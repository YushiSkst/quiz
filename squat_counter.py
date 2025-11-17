import cv2
import mediapipe as mp
import numpy as np
import time

# --- 初期設定 ---
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

# 検出信頼度を設定
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

cap = cv2.VideoCapture(0) # ウェブカメラを開く

# --- カウントと状態管理用の変数 ---
count = 0 
stage = None # 'up' (立ち上がっている) または 'down' (しゃがみ込んでいる)
current_rep_ok = False # 現在の動作がカウント対象かどうかのフラグ

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
                    count += 1
                    stage = "up"
            else:
                form_color = (0, 100, 255) # オレンジ色
            
            # --- 画面描画 ---
            
            # ランドマークと接続線の描画
            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                                     mp_drawing.DrawingSpec(color=(245,117,66), thickness=2, circle_radius=2), # 接続線の色
                                     mp_drawing.DrawingSpec(color=form_color, thickness=2, circle_radius=4) # ランドマークの色
                                    )
            
            # 角度表示 (デバッグ用)
            cv2.putText(image, f'Knee Angle: {int(knee_angle)}', (400, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
            
            # 状態表示
            cv2.putText(image, f'Stage: {stage.upper() if stage else "STAND"}', (400, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, form_color, 2, cv2.LINE_AA)
            
        except Exception as e:
            # ランドマークの一部が見つからない場合のエラーを無視
            pass
            
    # --- 回数カウントの表示 (左上) ---
    cv2.putText(image, 'REPS', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(image, str(count), (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3, cv2.LINE_AA)
    
    # 

    # ウィンドウ表示
    cv2.imshow("Squat Counter Trainer", image)
    
    # 'q'キーまたはESCキーで終了
    if cv2.waitKey(10) & 0xFF in [ord('q'), 27]:
        break

# 終了処理
cap.release()
cv2.destroyAllWindows()