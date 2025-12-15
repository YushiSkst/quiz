import cv2
import mediapipe as mp
import numpy as np
import sys  # ★追加

# 初期設定
mp_pose = mp.solutions.pose
# 姿勢検出モデルの初期化
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

# --- 引数処理と回数設定 ---
base_count = 14
penalty_per_wrong = 1  # 不正解1問につき1回追加
wrong_count = 0

if len(sys.argv) > 1:
    try:
        wrong_count = int(sys.argv[1])
    except ValueError:
        wrong_count = 0

# カウンターとステージの変数
counter = base_count + (wrong_count * penalty_per_wrong)
print(f"不正解数: {wrong_count}, 目標回数: {counter}回")

stage = None  # "down" または "up"
form_status = "Bad"  # フォームステータス

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
        
        # 上半身（肩・腰）の可視性チェック
        right_hip_vis = landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].visibility
        right_shoulder_vis = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].visibility
        is_upper_body_visible = (right_hip_vis > 0.5) and (right_shoulder_vis > 0.5)
        
        # 上半身が映っていない場合は stage をリセットしてカウントしない
        if not is_upper_body_visible:
            stage = None
        else:
            # ----------------------------------------------------
            # 2. 腕立て判定ロジック (角度に基づく) — 上半身が見えている場合のみ
            # ----------------------------------------------------
            # "down" フェーズ: 肘の角度が90度未満になったら
            if angle < 90:
                stage = "down"
            
            # "up" フェーズ: "down"から角度が160度より大きくなったらカウント
            if angle > 160 and stage == 'down':
                stage = "up"
                if counter > 0:  # 0より大きい場合のみカウントダウン
                    counter -= 1
                
                # 0に到達したらフォームを完了状態に
                if counter == 0:
                    form_status = "COMPLETED!"

        # ----------------------------------------------------
        # 3. フォームの簡易チェック (肩と腰の高さ比較) — 上半身が見えている場合のみ
        # ----------------------------------------------------
        if is_upper_body_visible:
            right_hip_y = landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y
            right_shoulder_y = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y
            y_diff = abs(right_shoulder_y - right_hip_y)
            is_form_correct = y_diff < 0.15
        else:
            # 上半身が見えていない場合はフォーム不良として扱う（表示等は既存ロジックに任せる）
            is_form_correct = False

        # ----------------------------------------------------
        # 4. 画面への情報表示
        # ----------------------------------------------------
        
        # ランドマークと接続線の描画
        mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        # 肘の角度表示
        cv2.putText(image, str(int(angle)),
                    (px_elbow[0] + 10, px_elbow[1]), # 肘の近くに表示
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
        
        # カウント＆フォーム表示（上部・中央揃え）
        top_margin = 30
        padding = 10

        # count ラベル（赤）と数値（白）を横並びで中央に配置
        count_label = 'count:'
        label_fs = 1
        label_th = 2
        label_size = cv2.getTextSize(count_label, cv2.FONT_HERSHEY_SIMPLEX, label_fs, label_th)[0]
        num_size = cv2.getTextSize(str(counter), cv2.FONT_HERSHEY_SIMPLEX, label_fs, label_th)[0]
        total_width = label_size[0] + 5 + num_size[0]
        count_x = (w - total_width) // 2
        count_y = top_margin + label_size[1]

        cv2.putText(image, count_label, (count_x, count_y),
                    cv2.FONT_HERSHEY_SIMPLEX, label_fs, (0, 0, 255), label_th, cv2.LINE_AA)
        cv2.putText(image, str(counter), (count_x + label_size[0] + 5, count_y),
                    cv2.FONT_HERSHEY_SIMPLEX, label_fs, (255, 255, 255), label_th, cv2.LINE_AA)

        # フォーム表示はその下に中央揃えで配置
        form_text = f'Form: {form_status}'
        form_fs = 1
        form_th = 2
        form_size = cv2.getTextSize(form_text, cv2.FONT_HERSHEY_SIMPLEX, form_fs, form_th)[0]
        form_x = (w - form_size[0]) // 2
        form_y = count_y + padding + form_size[1]
        form_color = (0, 255, 0) if is_form_correct else (0, 0, 255)
        cv2.putText(image, form_text, (form_x, form_y),
                    cv2.FONT_HERSHEY_SIMPLEX, form_fs, form_color, form_th, cv2.LINE_AA)


    # ウィンドウ表示
    cv2.imshow("Push-Up Counter", image)
    
    # カウンターが0になったら終了
    if counter == 0:
        cv2.waitKey(2000)  # 2秒間表示を保持
        break
    
    # 'q'キーで終了
    if cv2.waitKey(10) & 0xFF == ord('q'):
        break

# 終了処理
cap.release()
cv2.destroyAllWindows()