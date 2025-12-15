import cv2
import mediapipe as mp
import numpy as np
import sys  # ★追加

# --- 初期設定 ---
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

# 検出信頼度を設定
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

cap = cv2.VideoCapture(0) # ウェブカメラを開く

# --- 引数処理と回数設定 ---
base_count = 25
penalty_per_wrong = 2  # 不正解1問につき2回追加
wrong_count = 0

if len(sys.argv) > 1:
    try:
        wrong_count = int(sys.argv[1])
    except ValueError:
        wrong_count = 0

# --- カウントと状態管理用の変数 ---
count = base_count + (wrong_count * penalty_per_wrong)
print(f"不正解数: {wrong_count}, 目標回数: {count}回")

stage = None # 'up' (立ち上がっている) または 'down' (しゃがみ込んでいる)
current_rep_ok = False # 現在の動作がカウント対象かどうかのフラグ
form_color = (255, 255, 255)  # デフォルトの色（白）

# フォーム判定用の閾値
# 良いスクワットの目安：膝の角度が90度以下
SQUAT_THRESHOLD_ANGLE = 100 

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

def get_landmark_coords(landmarks, landmark_type):
    """ランドマークの座標を取得し、(x, y) リストとして返す"""
    lm = landmarks[landmark_type.value]
    # x, y座標は正規化されているため、画面サイズに合わせて調整する場合はここでh, wをかける
    return [lm.x, lm.y]

# --- メインループ ---
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
        
    frame = cv2.flip(frame, 1) # 左右反転（鏡として見せるため）
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image.flags.writeable = False # 処理効率化のために書き込み不可にする
    
    # 検出処理
    results = pose.process(image)
    
    image.flags.writeable = True # 描画のために書き込み可能に戻す
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    
    # 画像の幅と高さ
    h, w, c = image.shape
    
    # ランドマークが検出された場合
    if results.pose_landmarks:
        landmarks = results.pose_landmarks.landmark
        
        try:
            # フォームチェックに必要な座標を取得 (ここでは右半身を使用)
            # 股関節（HIP）、膝（KNEE）、足首（ANKLE）
            hip = get_landmark_coords(landmarks, mp_pose.PoseLandmark.RIGHT_HIP)
            knee = get_landmark_coords(landmarks, mp_pose.PoseLandmark.RIGHT_KNEE)
            ankle = get_landmark_coords(landmarks, mp_pose.PoseLandmark.RIGHT_ANKLE)

            # 全身が映っているかの可視性チェック
            shoulder_vis = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].visibility
            hip_vis = landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].visibility
            knee_vis = landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].visibility
            ankle_vis = landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].visibility
            is_body_visible = (shoulder_vis > 0.5) and (hip_vis > 0.5) and (knee_vis > 0.5) and (ankle_vis > 0.5)

            # 全身が見えていない場合はステージをリセット
            if not is_body_visible:
                stage = None
            else:
                # 膝の角度を計算（スクワットの深さを判断する主要な指標）
                knee_angle = calculate_angle(hip, knee, ankle)
                
                # --- 姿勢とカウントのロジック ---
                
                # 1. しゃがみ込み（DOWN）の判定
                # 膝の角度が閾値以下になったら、スクワットが成立
                if knee_angle < SQUAT_THRESHOLD_ANGLE:
                    stage = "down"
                    form_color = (0, 255, 255) # 黄色
                
                # 2. 立ち上がり（UP）の判定とカウントアップ
                # 'down' ステージから、十分に立ち上がった（膝の角度がほぼ180度）場合
                if knee_angle > 165:
                    form_color = (0, 255, 0) # 緑色
                    if stage == "down":
                        count -= 1  # カウントダウン
                        stage = "up"
                        # 0に到達したら終了
                        if count == 0:
                            stage = "COMPLETED!"
                else:
                    form_color = (0, 100, 255) # オレンジ色
                
                # --- 画面描画 ---
                
                # ランドマークと接続線の描画
                mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                                         mp_drawing.DrawingSpec(color=(245,117,66), thickness=2, circle_radius=2), # 接続線の色
                                         mp_drawing.DrawingSpec(color=form_color, thickness=2, circle_radius=4) # ランドマークの色
                                        )
                    
                # Stage表示（上部中央）
                stage_text = f'Stage: {stage.upper() if stage else "STAND"}'
                stage_fs = 1
                stage_th = 2
                stage_size = cv2.getTextSize(stage_text, cv2.FONT_HERSHEY_SIMPLEX, stage_fs, stage_th)[0]
                stage_x = (w - stage_size[0]) // 2
                stage_y = 30 + stage_size[1]
                cv2.putText(image, stage_text, (stage_x, stage_y),
                   cv2.FONT_HERSHEY_SIMPLEX, stage_fs, form_color, stage_th, cv2.LINE_AA)
                
        except Exception as e:
            # ランドマークの一部が見つからない場合のエラーを無視
            pass
            
    # --- 回数カウントの表示 (上部中央揃え) ---
    # Stage表示用の変数を先に初期化
    stage_text = f'Stage: {stage.upper() if stage else "STAND"}'
    stage_fs = 1
    stage_th = 2
    stage_size = cv2.getTextSize(stage_text, cv2.FONT_HERSHEY_SIMPLEX, stage_fs, stage_th)[0]
    stage_x = (w - stage_size[0]) // 2
    stage_y = 30 + stage_size[1]
    
    # ランドマークが検出されている場合のみ色を設定
    if results.pose_landmarks:
        cv2.putText(image, stage_text, (stage_x, stage_y),
           cv2.FONT_HERSHEY_SIMPLEX, stage_fs, form_color, stage_th, cv2.LINE_AA)
    else:
        cv2.putText(image, stage_text, (stage_x, stage_y),
           cv2.FONT_HERSHEY_SIMPLEX, stage_fs, (255, 255, 255), stage_th, cv2.LINE_AA)

    # count ラベル（赤）と数値（緑）を上部中央に配置
    top_margin = 30
    padding = 10
   
    count_label = 'count:'
    label_fs = 1
    label_th = 2
    label_size = cv2.getTextSize(count_label, cv2.FONT_HERSHEY_SIMPLEX, label_fs, label_th)[0]
    num_size = cv2.getTextSize(str(count), cv2.FONT_HERSHEY_SIMPLEX, label_fs, label_th)[0]
    total_width = label_size[0] + 5 + num_size[0]
    count_x = (w - total_width) // 2
    count_y = stage_y + padding + label_size[1]
   
    cv2.putText(image, count_label, (count_x, count_y),
               cv2.FONT_HERSHEY_SIMPLEX, label_fs, (0, 0, 255), label_th, cv2.LINE_AA)
    cv2.putText(image, str(count), (count_x + label_size[0] + 5, count_y),
               cv2.FONT_HERSHEY_SIMPLEX, label_fs, (0, 255, 0), label_th, cv2.LINE_AA)

    # ウィンドウ表示
    cv2.imshow("Squat Counter Trainer", image)
    
    # カウントが0以下になったら完了表示を出して終了
    if count <= 0:
        done_text = "COMPLETED!"
        fs = 1.5
        th = 3
        size = cv2.getTextSize(done_text, cv2.FONT_HERSHEY_SIMPLEX, fs, th)[0]
        x = (w - size[0]) // 2
        y = (h // 2) + size[1] // 2
        cv2.putText(image, done_text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, fs, (0, 255, 0), th, cv2.LINE_AA)
        cv2.imshow("Squat Counter Trainer", image)
        cv2.waitKey(2000)
        break

    # 'q'キーまたはESCキーで終了
    if cv2.waitKey(10) & 0xFF in [ord('q'), 27]:
        break

# 終了処理
cap.release()
cv2.destroyAllWindows()