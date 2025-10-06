import cv2
import mediapipe as mp
import numpy as np
import time

# --- 初期設定 ---
mp_pose = mp.solutions.pose
# 検出信頼度を設定
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

# --- タイマーとフォーム判定用の変数 ---
TARGET_TIME_SECONDS = 60 # 目標プランク時間（秒）
start_time = None        # プランク開始時の時刻
plank_active = False     # プランク姿勢が有効かどうかのフラグ

# フォーム判定用の閾値
HIP_ANGLE_MIN = 160  # 肩-腰-膝の角度がこの値以上ならフォーム良し（体が一直線に近い）
Y_OFFSET_MAX = 0.15  # 腰が肩や足首から大きく上下にずれていないかの許容範囲

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

def check_plank_form(landmarks):
    """
    プランクのフォームが正しいかチェックする関数
    
    1. 体の直線性チェック（肩-腰-膝の角度）
    2. 腰の高さチェック（肩と足首の中間位置に腰があるか）
    """
    try:
        # 1. 体の直線性チェック: 肩-腰-膝の角度
        shoulder = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x,
                    landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
        hip = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x,
               landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]
        knee = [landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x,
                landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y]

        hip_angle = calculate_angle(shoulder, hip, knee)
        is_straight = hip_angle > HIP_ANGLE_MIN
        
        # 2. 腰の高さチェック（簡易版: 腰のY座標が肩より極端に上がったり下がったりしていないか）
        # プランク姿勢では、y座標の値が小さいほど高い位置
        ankle_y = landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y
        shoulder_y = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y
        hip_y = landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y
        
        # 肩と足首の中間より腰が大きく逸脱していないか（簡易的に肩のY座標と比較）
        is_hip_level = abs(hip_y - (shoulder_y + ankle_y) / 2) < Y_OFFSET_MAX

        # 両方の条件を満たせばフォーム良し
        return is_straight and is_hip_level, hip_angle
        
    except Exception:
        # ランドマークが完全に検出できない場合はフォーム不良とする
        return False, 0


# --- メインループ ---
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
        
    frame = cv2.flip(frame, 1) # 左右反転（鏡として見せるため）
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # 検出処理
    results = pose.process(image)
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    
    # 画像の幅と高さ
    h, w, c = image.shape
    
    # 現在のプランク状態
    remaining_time = TARGET_TIME_SECONDS
    form_status = "Not Detected"
    
    # ランドマークが検出された場合
    if results.pose_landmarks:
        landmarks = results.pose_landmarks.landmark
        
        # フォームチェック
        is_plank_ready, hip_angle = check_plank_form(landmarks)
        
        # ----------------------------------------------------
        # プランク時間計測ロジック
        # ----------------------------------------------------
        if is_plank_ready:
            form_status = "Good"
            
            # プランク開始
            if not plank_active:
                plank_active = True
                start_time = time.time()
                
            # 時間計算
            elapsed_time = time.time() - start_time
            remaining_time = max(0, TARGET_TIME_SECONDS - elapsed_time)
            
            # カウントダウン完了
            if remaining_time <= 0:
                plank_active = False
                form_status = "COMPLETED!"
                remaining_time = 0
                
        else:
            # フォーム不良またはプランク姿勢を解除
            form_status = "Bad Form / Reset"
            plank_active = False
            start_time = None
            remaining_time = TARGET_TIME_SECONDS
            
        # ----------------------------------------------------
        # 画面表示
        # ----------------------------------------------------
        
        # ランドマークと接続線の描画
        mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        # フォーム判定表示
        form_color = (0, 255, 0) if form_status == "Good" or form_status == "COMPLETED!" else (0, 0, 255)
        cv2.putText(image, f'Form: {form_status}', (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, form_color, 2, cv2.LINE_AA)
        
        # 角度表示 (デバッグ用)
        cv2.putText(image, f'Hip Angle: {int(hip_angle)}', (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 1, cv2.LINE_AA)


    # カウントダウンタイマー表示 (中央上部)
    timer_text = f'{int(remaining_time)} sec'
    if remaining_time == 0 and form_status == "COMPLETED!":
        timer_text = "SUCCESS!"
        timer_color = (255, 0, 0)
    elif plank_active:
        timer_color = (0, 255, 255) # 黄色
    else:
        timer_color = (255, 255, 255) # 白

    # テキストサイズを取得して中央に配置
    text_size = cv2.getTextSize(timer_text, cv2.FONT_HERSHEY_SIMPLEX, 2, 3)[0]
    text_x = (w - text_size[0]) // 2
    cv2.putText(image, timer_text, (text_x, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 2, timer_color, 3, cv2.LINE_AA)

    # ウィンドウ表示
    cv2.imshow("Plank Countdown Trainer", image)
    
    # 'q'キーで終了
    if cv2.waitKey(10) & 0xFF == ord('q'):
        break

# 終了処理
cap.release()
cv2.destroyAllWindows()