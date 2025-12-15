# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox
import subprocess
import json
import re
import unicodedata
import httpx
from openai import OpenAI
import random
import os
import pandas as pd
import threading

# ───────────────────────────────
# 設定・定数
# ───────────────────────────────
# AI設定
API_BASE_URL = "http://192.168.19.1:11434/v1"
API_KEY = "fake-key"
MODEL_NAME = "gemma3:27b-it-q4_K_M"

# GUI設定
COLOR_BG = "#e8f5e9"        # 背景色（薄い緑）
COLOR_TITLE = "#1b5e20"     # タイトル文字色（濃い緑）
COLOR_BTN_MAIN = "#66bb6a"  # メインボタン背景
COLOR_BTN_TEXT = "white"    # メインボタン文字
COLOR_TEXT_MAIN = "#2e7d32"

# 運動プログラムの定義（表示名: ファイル名）
EXERCISE_PROGRAMS = {
    "プランク": "plank_trainer.py",
    "プッシュアップ": "pushup_counter.py",
    "スクワット": "squat_counter.py"
}

# ───────────────────────────────
# ① ロジッククラス（問題生成・正誤判定・履歴管理）
# ───────────────────────────────
class QuizLogic:
    """
    AIとの通信やクイズの正誤判定、Excel読み込みを担当するクラス
    """
    def __init__(self):
        self.client = OpenAI(
            base_url=API_BASE_URL,
            api_key=API_KEY,
            http_client=httpx.Client(verify=False, timeout=120.0),
        )
        # 使用済みデータの行番号を記録するリスト（データ被り防止用）
        self.used_indices = []

    def reset_history(self):
        """履歴をリセットする"""
        self.used_indices = []

    def load_random_excel_data(self, filepath, num_samples=20):
        """
        Excelファイルを読み込み、まだ使っていない行からランダムにデータを抽出
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"ファイルが見つかりません: {filepath}")

        try:
            df = pd.read_excel(filepath, header=None)
            
            if df.empty:
                return "データがありません。"

            total_rows = len(df)
            
            # まだ使っていない行のインデックスを取得
            available_indices = [i for i in range(total_rows) if i not in self.used_indices]
            
            # もし未使用データが足りなければ、履歴をリセットして全データから選ぶ
            if len(available_indices) < num_samples:
                print("データが一巡しました。履歴をリセットして再利用します。")
                self.used_indices = []
                available_indices = list(range(total_rows))

            # 利用可能な行からランダムにインデックスを選択
            current_sample_size = min(len(available_indices), num_samples)
            selected_indices = random.sample(available_indices, current_sample_size)
            
            # 選んだインデックスを使用済みリストに追加
            self.used_indices.extend(selected_indices)

            # 選んだ行のデータを抽出
            sampled_df = df.iloc[selected_indices]
            
            print(f"使用した行番号: {selected_indices}") # デバッグ用
            return sampled_df.to_csv(index=False, header=False)

        except Exception as e:
            raise RuntimeError(f"Excel読み込みエラー: {e}")

    def generate_quiz_batch(self, difficulty, filename, num_questions=10):
        """
        指定されたExcelファイルの内容に基づいて、指定数分の問題を【一括生成】する
        """
        # Excelデータを取得（履歴管理機能付き）
        try:
            data_content = self.load_random_excel_data(filename, num_samples=30)
        except Exception as e:
            print(e)
            return None

        # プロンプト作成
        base_instruction = f"""
        あなたはプロのクイズ作家です。
        以下の【学習データ】の内容**のみ**に基づいて、多様なクイズを作成してください。
        （前回とは違う箇所のデータを使用しています）
        
        ## 🤖 クイズ生成の絶対ルール
        1. **正解の重複禁止**: 全{num_questions}問において、正解となる単語はすべて異なるものにすること。
        2. **問題文の重複禁止(重要)**: すべての問題文（question）は、言い回しや問う内容を変え、**1つとして同じ文章にしてはいけません**。
        3. **配置のランダム化**: 選択肢の正解位置はランダムにすること。
        4. **JSON配列で出力**: 指定された問題数を、1つのJSON配列（リスト）として出力すること。

        【学習データ】
        {data_content}
        """

        if difficulty == "初級":
            prompt = base_instruction + f"""
            初級レベルの三択問題を**{num_questions}問**生成してください。
            
            ### 出力例（このように異なる問題文を作成すること）:
            [
              {{
                "question": "CPUの役割として正しいものはどれか？",
                "choices": ["演算処理", "記憶", "入力"],
                "answer": "演算処理"
              }},
              {{
                "question": "データを一時的に保存する装置は何か？",
                "choices": ["HDD", "メモリ", "マウス"],
                "answer": "メモリ"
              }}
            ]
            
            以下の形式のJSON配列のみを出力してください（Markdown記法は不要）：
            """
        elif difficulty == "中級":
            prompt = base_instruction + f"""
            中級レベルの単語入力問題（記述式）を**{num_questions}問**生成してください。
            答えは学習データに含まれる単語にしてください。
            
            ### 出力例（このように異なる問題文を作成すること）:
            [
              {{
                "question": "コンピュータの頭脳と呼ばれる装置は何か？",
                "answer": "CPU"
              }},
              {{
                "question": "Webサイトを閲覧するために使うソフトは？",
                "answer": "ブラウザ"
              }}
            ]
            
            以下の形式のJSON配列のみを出力してください（Markdown記法は不要）：
            """

        # --- AI 実行 ---
        try:
            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8, # 多様性を出すために少し高め
            )
            text = response.choices[0].message.content

            # --- JSON抽出 ---
            match = re.search(r"\[\s*\{[\s\S]*\}\s*\]", text)
            if not match:
                match = re.search(r"\{[\s\S]*\}", text)
                if not match: return None
            
            json_str = match.group()
            raw_quiz_list = json.loads(json_str)

            # --- Python側での重複排除（安全装置） ---
            unique_quiz_list = []
            seen_questions = set()
            
            for quiz in raw_quiz_list:
                q_text = quiz.get("question", "")
                # 問題文が既に存在する場合はスキップ
                if q_text not in seen_questions:
                    unique_quiz_list.append(quiz)
                    seen_questions.add(q_text)

            return unique_quiz_list
            
        except Exception as e:
            print(f"Error generating quiz: {e}")
            return None

    def check_answer(self, difficulty, quiz, user_answer):
        """ユーザーの回答を判定する"""
        if difficulty == "初級":
            return user_answer == quiz["answer"]

        elif difficulty == "中級":
            def normalize(t):
                # 全角・半角や大文字・小文字を統一して比較
                t = unicodedata.normalize("NFKC", t.lower())
                return "".join(
                    c for c in t if c.isalnum() or "\u3040" <= c <= "\u9faf"
                )
            return normalize(user_answer) in normalize(quiz["answer"])

        return False


# ───────────────────────────────
# ② GUIクラス（画面描画）
# ───────────────────────────────
class QuizApp:
    def __init__(self, root):
        self.root = root
        self.logic = QuizLogic() 
        
        # 基本ウィンドウ設定
        root.title("Excelデータ クイズ生成機")
        root.geometry("600x650")
        root.configure(bg=COLOR_BG)

        # 状態管理変数
        self.difficulty_var = tk.StringVar(value="初級")
        self.file_var = tk.StringVar(value="data.xlsx") 
        
        # クイズデータ管理用
        self.quiz_list = []      # 生成された全問題リスト
        self.current_quiz = None # 現在出題中の問題
        self.question_index = 0  # 現在何問目か (0始まり)
        
        self.correct_count = 0
        self.wrong_count = 0
        self.quiz_frame = None
        self.loading_label = None

        # スタート画面の描画
        self.setup_start_screen()

    def setup_start_screen(self):
        """スタート画面（設定画面）の構築"""
        for widget in self.root.winfo_children():
            widget.destroy()

        # タイトル
        tk.Label(
            self.root, text="IT学習 クイズ",
            font=("Yu Gothic", 24, "bold"),
            bg=COLOR_BG, fg=COLOR_TITLE
        ).pack(pady=20)

        # 難易度設定
        tk.Label(self.root, text="難易度を選択してください", bg=COLOR_BG, font=("Yu Gothic", 12)).pack(pady=(20, 5))

        radio_frame = tk.Frame(self.root, bg=COLOR_BG)
        radio_frame.pack(pady=5)

        tk.Radiobutton(
            radio_frame, text="初級 (3択)", variable=self.difficulty_var, value="初級",
            bg=COLOR_BG, activebackground=COLOR_BG, font=("Yu Gothic", 11)
        ).pack(side=tk.LEFT, padx=10)

        tk.Radiobutton(
            radio_frame, text="中級 (記述)", variable=self.difficulty_var, value="中級",
            bg=COLOR_BG, activebackground=COLOR_BG, font=("Yu Gothic", 11)
        ).pack(side=tk.LEFT, padx=10)

        # スタートボタン
        tk.Button(
            self.root, text="問題を生成して開始",
            font=("Yu Gothic", 12, "bold"),
            bg=COLOR_BTN_MAIN, fg=COLOR_BTN_TEXT,
            command=self.prepare_quiz_start, # 準備処理へ
            width=20, height=2
        ).pack(pady=40)

    def prepare_quiz_start(self):
        """クイズ開始前の準備（ロード画面表示とデータ生成）"""
        self.difficulty = self.difficulty_var.get()
        self.filename = self.file_var.get()
        
        if not os.path.exists(self.filename):
            messagebox.showerror("エラー", f"ファイル '{self.filename}' が見つかりません。\n実行フォルダに配置してください。")
            return

        # 画面を一度クリア
        for widget in self.root.winfo_children():
            widget.destroy()
            
        # ロード画面のラベルを保持
        self.loading_label = tk.Label(
            self.root, text="AIが問題を生成しています...\n(10問作成中)", 
            font=("Yu Gothic", 16), bg=COLOR_BG, fg=COLOR_TEXT_MAIN
        )
        self.loading_label.pack(expand=True)
        
        self.root.update() # 画面描画を更新

        # 処理ブロック防止のため、少し待ってからデータ生成へ
        self.root.after(100, self.generate_and_start)

    def generate_and_start(self):
        """AIを使って一括生成し、完了したらクイズ画面へ"""
        # AI処理（時間がかかる）
        quiz_data = self.logic.generate_quiz_batch(self.difficulty, self.filename, num_questions=10)
        
        # ロード画面を確実に削除
        if hasattr(self, 'loading_label') and self.loading_label:
            self.loading_label.destroy()
            self.loading_label = None

        if not quiz_data or not isinstance(quiz_data, list):
            messagebox.showerror("エラー", "問題生成に失敗しました。\nもう一度お試しください。")
            self.setup_start_screen()
            return
        
        if len(quiz_data) == 0:
            messagebox.showerror("エラー", "問題が生成されませんでした。\nExcelデータを確認してください。")
            self.setup_start_screen()
            return

        # 変数リセット
        self.quiz_list = quiz_data
        self.question_index = 0
        self.correct_count = 0
        self.wrong_count = 0
        
        # クイズ画面へ
        self.show_next_question()

    def show_next_question(self):
        """次の問題を表示"""
        if self.quiz_frame:
            self.quiz_frame.destroy()

        # 全問終了チェック
        if self.question_index >= len(self.quiz_list):
            self.show_final_result()
            return

        # 現在の問題を取得
        self.current_quiz = self.quiz_list[self.question_index]

        # --- UI 構築 ---
        self.quiz_frame = tk.Frame(self.root, bg=COLOR_BG)
        self.quiz_frame.pack(pady=20, fill="both", expand=True)

        # 問題番号
        tk.Label(
            self.quiz_frame, text=f"第 {self.question_index + 1} 問 / 全{len(self.quiz_list)}問",
            bg=COLOR_BG, fg=COLOR_TEXT_MAIN, font=("Yu Gothic", 16, "bold")
        ).pack(pady=5)

        # 問題文
        tk.Label(
            self.quiz_frame, text=self.current_quiz["question"],
            wraplength=500, justify="center",
            bg=COLOR_BG, font=("Yu Gothic", 14)
        ).pack(pady=10)

        # 選択肢または入力欄の表示
        if self.difficulty == "初級":
            self.create_choice_buttons(self.current_quiz)
        else:
            self.create_input_field()

    def create_choice_buttons(self, quiz):
        """初級用：三択ボタンの生成"""
        choices = quiz["choices"]
        labels = ["A", "B", "C"]
        
        for label, text in zip(labels, choices):
            tk.Button(
                self.quiz_frame,
                text=f"{label}: {text}",
                bg="#81c784", fg="black",
                font=("Yu Gothic", 12),
                width=40, height=2,
                wraplength=350,
                command=lambda x=text: self.check_answer_gui(x)
            ).pack(pady=5)

    def create_input_field(self):
        """中級用：入力フィールドの生成"""
        self.entry = tk.Entry(self.quiz_frame, font=("Yu Gothic", 14), width=30)
        self.entry.pack(pady=10, ipady=5)
        self.entry.focus_set() # フォーカスを当てる

        # Enterキーでも回答できるようにする
        self.root.bind('<Return>', lambda event: self.check_answer_gui(self.entry.get()))

        tk.Button(
            self.quiz_frame, text="回答する",
            bg="#fbc02d", fg="black",
            font=("Yu Gothic", 14, "bold"),
            width=20, height=2,
            command=lambda: self.check_answer_gui(self.entry.get())
        ).pack(pady=10)

    def check_answer_gui(self, user_answer):
        """回答チェックと中間結果表示"""
        # Enterキーバインドを解除（二重送信防止）
        self.root.unbind('<Return>')
        
        is_correct = self.logic.check_answer(self.difficulty, self.current_quiz, user_answer)

        if is_correct:
            messagebox.showinfo("結果", "正解！")
            self.correct_count += 1
        else:
            messagebox.showinfo("結果", f"不正解…\n正解は「{self.current_quiz['answer']}」です。")
            self.wrong_count += 1

        self.question_index += 1
        self.show_next_question()

    def show_final_result(self):
        """全問終了後の結果画面"""
        if self.quiz_frame:
            self.quiz_frame.destroy()

        result_frame = tk.Frame(self.root, bg=COLOR_BG)
        result_frame.pack(pady=50, fill="both", expand=True)

        # 結果テキスト
        tk.Label(
            result_frame, text="クイズ終了！",
            bg=COLOR_BG, fg=COLOR_TITLE, font=("Yu Gothic", 24, "bold")
        ).pack(pady=20)

        result_text = f"正解：{self.correct_count}問\n不正解：{self.wrong_count}問"
        tk.Label(
            result_frame, text=result_text,
            bg=COLOR_BG, font=("Yu Gothic", 18)
        ).pack(pady=20)

        # 再挑戦ボタン
        tk.Button(
            result_frame, text="タイトルに戻る",
            bg=COLOR_BTN_MAIN, fg=COLOR_BTN_TEXT,
            font=("Yu Gothic", 12),
            width=20,
            command=self.setup_start_screen
        ).pack(pady=10)

        # 終了して運動するボタン
        tk.Button(
            result_frame, text="終了して運動する",
            bg="#ef5350", fg="white",
            font=("Yu Gothic", 12, "bold"),
            width=20,
            command=self.open_exercise_selector # 変更箇所: 選択画面を開く
        ).pack(pady=20)

    # ───────────────────────────────
    # ★追加: 運動プログラム選択機能
    # ───────────────────────────────
    def open_exercise_selector(self):
        """運動プログラム選択ウィンドウを開く"""
        self.selector_window = tk.Toplevel(self.root)
        self.selector_window.title("運動を選択")
        self.selector_window.geometry("300x250")
        self.selector_window.configure(bg=COLOR_BG)

        tk.Label(
            self.selector_window, text="どの運動を行いますか？",
            font=("Yu Gothic", 14, "bold"), bg=COLOR_BG, fg=COLOR_TITLE
        ).pack(pady=20)

        # 選択メニュー用の変数
        self.selected_exercise = tk.StringVar(self.selector_window)
        # 辞書から運動名のリストを取得
        exercise_names = list(EXERCISE_PROGRAMS.keys())
        self.selected_exercise.set(exercise_names[0]) # デフォルト値

        # ドロップダウンメニュー
        option_menu = tk.OptionMenu(self.selector_window, self.selected_exercise, *exercise_names)
        option_menu.config(font=("Yu Gothic", 12), bg="white", width=15)
        option_menu.pack(pady=10)

        # 実行ボタン
        tk.Button(
            self.selector_window, text="決定して開始",
            font=("Yu Gothic", 12, "bold"),
            bg=COLOR_BTN_MAIN, fg=COLOR_BTN_TEXT,
            command=self.run_selected_exercise_and_exit,
            width=15
        ).pack(pady=20)

    def run_selected_exercise_and_exit(self):
        """選択された運動プログラムを実行して終了"""
        exercise_name = self.selected_exercise.get()
        program_file = EXERCISE_PROGRAMS.get(exercise_name)

        if not program_file:
            messagebox.showerror("エラー", "プログラムが見つかりません。")
            return

        # メインウィンドウと選択ウィンドウを破棄
        self.selector_window.destroy()
        self.root.destroy()

        try:
            # 外部プログラムを実行
            subprocess.run(["python", program_file])
        except FileNotFoundError:
            print(f"エラー: {program_file} が見つかりませんでした。")
        except Exception as e:
            print(f"実行エラー: {e}")


# ───────────────────────────────
# ③ メイン実行処理
# ───────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = QuizApp(root)
    root.mainloop()