import cv2
import mediapipe as mp
import numpy as np

# 初期設定
mp_pose = mp.solutions.pose
# 姿勢検出モデルの初期化 (精度を高めるためにstatic_image_mode=Falseが一般的だが、
# ここではデフォルト設定のままで進めます)
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

# カウンターとステージの変数
counter = 0
stage = None  # "down" または "up"

def calculate_angle(a, b, c):
    """3点の角度を計算（Bを中心とした角度）"""
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    
    # ベクトルBAとBCのなす角を計算
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)
    
    # 角度を常に180度以下にする
    if angle > 180.0:
        angle = 360 - angle
        
    return angle

cap = cv2.VideoCapture(0)

# メインループ
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
        
    # 処理のために画像を反転し、色空間をBGRからRGBに変換
    frame = cv2.flip(frame, 1)
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # 検出処理
    results = pose.process(image)
    
    # 色空間をRGBからBGRに戻す（表示用）
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    if results.pose_landmarks:
        landmarks = results.pose_landmarks.landmark
        
        # 画像の幅と高さを取得（正規化座標をピクセル座標に戻すため）
        h, w, c = image.shape

        # ----------------------------------------------------
        # 1. 肘の角度計算
        # ----------------------------------------------------
        # 肩、肘、手首の正規化座標を取得（今回は右腕を検出対象とする）
        shoulder = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x,
                    landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
        elbow = [landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x,
                 landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y]
        wrist = [landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x,
                 landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y]

        angle = calculate_angle(shoulder, elbow, wrist)

        # 肘のピクセル座標（角度表示用）
        px_elbow = (int(elbow[0] * w), int(elbow[1] * h))
        
        # ----------------------------------------------------
        # 2. 腕立て判定ロジック (角度に基づく)
        # ----------------------------------------------------
        # "down" フェーズ: 肘の角度が90度未満になったら
        if angle < 90:
            stage = "down"
            
        # "up" フェーズ: "down"から角度が160度より大きくなったらカウント
        if angle > 160 and stage == 'down':
            stage = "up"
            counter += 1

        # ----------------------------------------------------
        # 3. フォームの簡易チェック (肩と腰の高さ比較)
        # ----------------------------------------------------
        right_hip_y = landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y
        right_shoulder_y = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y
        
        # 簡易的なチェック: 肩と腰のY座標の差が一定値以内ならOK
        # 腕立て伏せの際は、Y座標の値が小さいほど高い位置
        y_diff = abs(right_shoulder_y - right_hip_y)
        
        # 0.1は調整可能な閾値
        is_form_correct = y_diff < 0.15 

        # ----------------------------------------------------
        # 4. 画面への情報表示
        # ----------------------------------------------------
        
        # ランドマークと接続線の描画
        mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        # 肘の角度表示
        cv2.putText(image, str(int(angle)),
                    (px_elbow[0] + 10, px_elbow[1]), # 肘の近くに表示
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
        
        # カウント表示 (左上)
        cv2.putText(image, f'Push-ups: {counter}', (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    
        # ステージ表示 (左上)
        stage_color = (0, 255, 0) if stage == "up" else (0, 0, 255)
        cv2.putText(image, f'Stage: {stage}', (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, stage_color, 2)
                    
        # フォームチェック結果表示 (左上)
        form_color = (0, 255, 0) if is_form_correct else (0, 0, 255) # 緑または赤
        cv2.putText(image, f'Form: {"Good" if is_form_correct else "Bad"}', (10, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, form_color, 2)


    # ウィンドウ表示
    cv2.imshow("Push-Up Counter", image)
    
    # 'q'キーで終了
    if cv2.waitKey(10) & 0xFF == ord('q'):
        break

# 終了処理
cap.release()
cv2.destroyAllWindows()