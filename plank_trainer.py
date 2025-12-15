import cv2
import mediapipe as mp
import numpy as np
import time
import sys  # ★追加: 引数受け取り用

# --- 初期設定 ---
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

# 検出信頼度を設定
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

cap = cv2.VideoCapture(0)

# --- 引数処理とタイマー設定 ---
# デフォルト値
base_time = 30
penalty_per_wrong = 3  # 不正解1問につき3秒追加
wrong_count = 0

# コマンドライン引数から不正解数を取得
if len(sys.argv) > 1:
    try:
        wrong_count = int(sys.argv[1])
    except ValueError:
        wrong_count = 0

TARGET_TIME_SECONDS = base_time + (wrong_count * penalty_per_wrong)
print(f"不正解数: {wrong_count}, 目標時間: {TARGET_TIME_SECONDS}秒")

# --- タイマーとフォーム判定用の変数 ---
plank_time_accumulated = 0.0 # フォーム良しでプランクを行った累積時間
last_good_form_time = None   # 最後にフォームが「Good」であった時の時刻
is_counting = False          # 現在カウントが進行しているかどうかのフラグ

# フォーム判定用の閾値
HIP_ANGLE_MIN = 160      # 肩-腰-膝の角度 (体が一直線に近いほど良い)
Y_OFFSET_MAX_LINE = 0.05 # 肩-足首の直線からの腰の許容誤差（正規化座標）

# --- ユーティリティ関数 ---
def calculate_angle(a, b, c):
    """3点の角度を計算（Bを中心とした角度）"""
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)
    
    if angle > 180.0:
        angle = 360 - angle
        
    return angle

def distance_point_to_line(p, a, b):
    """点 p(x0, y0) から、点 a と b を通る直線までの垂直距離を計算"""
    p = np.array(p)
    a = np.array(a)
    b = np.array(b)
    
    if np.array_equal(a, b):
        return np.linalg.norm(p - a)
        
    A = b[1] - a[1]
    B = a[0] - b[0]
    C = a[0]*b[1] - b[0]*a[1]
    
    distance = np.abs(A * p[0] + B * p[1] + C) / np.sqrt(A**2 + B**2 + 1e-6)
    return distance

def check_plank_form(landmarks):
    """
    プランクのフォームが正しいかチェックする関数
    
    肩-腰-膝の直線性、肩-足首の直線に対する腰の高さ、山なり防止をチェック
    """
    try:
        # ランドマーク座標 (正規化された[0, 1]の値)
        shoulder = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x,
                    landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
        hip = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x,
               landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]
        knee = [landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x,
                landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y]
        ankle = [landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].x,
                 landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y] 

        # 1. 体の直線性チェック: 肩-腰-膝の角度
        hip_angle = calculate_angle(shoulder, hip, knee)
        is_straight = hip_angle > HIP_ANGLE_MIN
        
        # 2. 腰の高さチェック (肩-足首の直線からの垂直距離)
        dist_from_line = distance_point_to_line(hip, shoulder, ankle)
        is_hip_level = dist_from_line < Y_OFFSET_MAX_LINE
        
        # 3. 腰が極端に高すぎないかのチェック (山なり防止)
        is_not_too_high = hip[1] > shoulder[1] - Y_OFFSET_MAX_LINE 

        is_good_form = is_straight and is_hip_level and is_not_too_high
        
        return is_good_form, hip_angle
        
    except Exception:
        return False, 0

def check_visibility(landmarks, threshold=0.8):
    """
    上半身の主要ランドマーク（肩、肘、腰）の可視性をチェック
    """
    # 右側でのチェック
    is_right_visible = all(landmarks[lm.value].visibility > threshold for lm in [mp_pose.PoseLandmark.RIGHT_SHOULDER, mp_pose.PoseLandmark.RIGHT_ELBOW, mp_pose.PoseLandmark.RIGHT_HIP])
    
    # 左側でのチェック
    is_left_visible = all(landmarks[lm.value].visibility > threshold for lm in [mp_pose.PoseLandmark.LEFT_SHOULDER, mp_pose.PoseLandmark.LEFT_ELBOW, mp_pose.PoseLandmark.LEFT_HIP])

    return is_right_visible or is_left_visible


# --- メインループ ---
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
        
    frame = cv2.flip(frame, 1) # 左右反転（鏡として見せるため）
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image.flags.writeable = False 
    
    # 検出処理
    results = pose.process(image)
    
    image.flags.writeable = True 
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    
    # 画像の幅と高さ
    h, w, c = image.shape
    
    # 初期状態の設定
    hip_angle = 0
    remaining_time = max(0, TARGET_TIME_SECONDS - plank_time_accumulated)
    form_status = "Not Detected"
    
    # ランドマークが検出された場合
    if results.pose_landmarks:
        landmarks = results.pose_landmarks.landmark
        
        # ----------------------------------------------------
        # プランク開始条件（上半身検出）と時間計測ロジック
        # ----------------------------------------------------
        
        # 0. 上半身可視性のチェック
        is_fully_visible = check_visibility(landmarks)
        
        if is_fully_visible:
            # 1. フォームチェック
            is_plank_ready, hip_angle = check_plank_form(landmarks)

            if is_plank_ready:
                form_status = "Good"
                
                # プランクカウント再開/開始
                if not is_counting:
                    is_counting = True
                    last_good_form_time = time.time()
                
                # 時間計算 (累積加算)
                current_time = time.time()
                time_diff = current_time - last_good_form_time
                plank_time_accumulated += time_diff
                last_good_form_time = current_time

            else:
                # フォーム不良 or 足首が映ってない -> カウント一時停止
                form_status = "Bad Form / Adjust View"
                is_counting = False
                last_good_form_time = None

        else:
            # 上半身が映っていない -> カウント一時停止
            form_status = "Can't Scan you'r Full Body "
            is_counting = False
            last_good_form_time = None
            
        # 2. 完了判定
        if plank_time_accumulated >= TARGET_TIME_SECONDS:
            is_counting = False
            form_status = "COMPLETED!"
            plank_time_accumulated = TARGET_TIME_SECONDS
        
        # 3. 残り時間の計算
        remaining_time = max(0, TARGET_TIME_SECONDS - plank_time_accumulated)


        # ----------------------------------------------------
        # 画面表示
        # ----------------------------------------------------
        
        # ランドマークと接続線の描画
        mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        # フォーム判定表示（中央揃え）
        # form_text = f'Form: {form_status}'
        # form_font_scale = 1
        # form_thickness = 2
        # form_color = (0, 255, 0) if form_status == "Good" or form_status == "COMPLETED!" else (0, 0, 255)
        # form_size = cv2.getTextSize(form_text, cv2.FONT_HERSHEY_SIMPLEX, form_font_scale, form_thickness)[0]
        # form_x = (w - form_size[0]) // 2
        # # タイマーを画面中央に配置するので、フォームはその上に表示
        # # フォームのY位置はタイマーのY位置に応じて下で設定するため一旦仮設定
        # form_y = 0
        # cv2.putText(image, form_text, (form_x, form_y if form_y>0 else 40),
        #             cv2.FONT_HERSHEY_SIMPLEX, form_font_scale, form_color, form_thickness, cv2.LINE_AA)

    # カウントダウンタイマー表示 (中央)
    # 分と秒に変換
    minutes = int(remaining_time // 60)
    seconds = int(remaining_time % 60)
    
    timer_text_value = f'{minutes:02d}:{seconds:02d}' # 例: 00:30
    timer_font_scale = 2
    timer_thickness = 3

    if form_status == "COMPLETED!":
        display_text = "SUCCESS!"
        timer_color = (255, 0, 0)
    else:
        display_text = "TIME " + timer_text_value
        timer_color = (0, 255, 255) if is_counting else (255, 255, 255)

    # テキストサイズを取得して中央に配置（横・縦）
    text_size = cv2.getTextSize(display_text, cv2.FONT_HERSHEY_SIMPLEX, timer_font_scale, timer_thickness)[0]
    text_x = (w - text_size[0]) // 2
    # Yは画面中央に設定（テキストの高さを考慮して基準を調整）
    text_y = h // 2 + text_size[1] // 2

    # フォームはタイマーの上に配置（重ならないように調整）
    # 先に計算しておいた form_x を使い、form_y をタイマーの上に設定
    form_y = text_y - 80
    if form_y < 30:
        form_y = 30

    # フォーム表示（再描画、中央X位置を使う）
    # form_text = f'Form: {form_status}'
    # form_font_scale = 1
    # form_thickness = 2
    # form_color = (0, 255, 0) if form_status == "Good" or form_status == "COMPLETED!" else (0, 0, 255)
    # form_size = cv2.getTextSize(form_text, cv2.FONT_HERSHEY_SIMPLEX, form_font_scale, form_thickness)[0]
    # form_x = (w - form_size[0]) // 2
    # cv2.putText(image, form_text, (form_x, form_y),
    #             cv2.FONT_HERSHEY_SIMPLEX, form_font_scale, form_color, form_thickness, cv2.LINE_AA)

    # 上部に横中央揃えで表示
    top_margin = 30
    padding = 8

    # フォーム表示（上部・中央）
    form_text = f'Form: {form_status}'
    form_font_scale = 1
    form_thickness = 2
    form_color = (0, 255, 0) if form_status in ("Good", "COMPLETED!") else (0, 0, 255)
    form_size = cv2.getTextSize(form_text, cv2.FONT_HERSHEY_SIMPLEX, form_font_scale, form_thickness)[0]
    form_x = (w - form_size[0]) // 2
    # baseline の分だけ下げて表示（トップマージンからテキスト高さ分）
    form_y = top_margin + form_size[1]
    cv2.putText(image, form_text, (form_x, form_y),
                cv2.FONT_HERSHEY_SIMPLEX, form_font_scale, form_color, form_thickness, cv2.LINE_AA)

    # タイマー表示（フォームの下に配置、中央揃え）
    timer_font_scale = 2
    timer_thickness = 3
    if form_status == "COMPLETED!":
        display_text = "SUCCESS!"
        timer_color = (255, 0, 0)
    else:
        display_text = "TIME " + timer_text_value
        timer_color = (0, 255, 255) if is_counting else (255, 255, 255)

    timer_size = cv2.getTextSize(display_text, cv2.FONT_HERSHEY_SIMPLEX, timer_font_scale, timer_thickness)[0]
    timer_x = (w - timer_size[0]) // 2
    timer_y = form_y + padding + timer_size[1]
    cv2.putText(image, display_text, (timer_x, timer_y),
                cv2.FONT_HERSHEY_SIMPLEX, timer_font_scale, timer_color, timer_thickness, cv2.LINE_AA)

    # ウィンドウ表示
    cv2.imshow("Plank Countdown Trainer", image)
    
    # タイマーが0になったら表示を短く保持して終了
    if remaining_time <= 0 or form_status == "COMPLETED!":
        cv2.waitKey(2000)
        break

    # 'q'キーで終了
    if cv2.waitKey(10) & 0xFF == ord('q'):
        break

# 終了処理
cap.release()
cv2.destroyAllWindows()