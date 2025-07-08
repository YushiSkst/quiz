import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk  # OptionMenuのためにインポート
import subprocess  # ファイルの冒頭（他のimportの下）に追加

# --- ゲーム設定 ---
GAME_TITLE = "Tkinter 総合クイズ"
FONT_FAMILY = "Yu Gothic UI"
FONT_SIZE_S = 12
FONT_SIZE_M = 16
FONT_SIZE_L = 24

# --- クイズデータ ---
# ジャンルと難易度で管理する新しいデータ構造
ALL_QUIZZES = {
    "プログラミング基礎": {
        "初級": [
            {
                "type": "choice",
                "question": "以下の３つの中で、主にwebページの装飾をする用途で用いられる言語は？",
                "choices": ["1. Java", "2. CSS", "3. C#"],
                "correct_choice_index": 1,
            },
            {
                "type": "fill_in",
                "question": "Pythonでリストの要素数を取得する関数は len() ですが、文字列の長さを取得する場合も同じ関数を使います。この関数 len は何の略でしょう？",
                "answer": "length",
            },
            {
                "type": "choice",
                "question": "プログラミングにおいて、同じ処理を何度も繰り返す構造を何と呼びますか？",
                "choices": ["1. 条件分岐", "2. ループ", "3. 変数"],
                "correct_choice_index": 1,
            },
        ]
    },
    "プログラミング実践 (Python)": {
        "未実装": [
            {
                "type": "fill_in",
                "question": "あなたの名前と年齢をそれぞれnameとageという変数に代入し、print()関数を使って「（名前）さんの年齢は（年齢）歳です。」と表示するプログラムを作成してください。",
                "answer": "with open",
            },
            {
                "type": "fill_in",
                "question": "リスト `numbers = [1, 2, 3, 4]` の各要素を2乗した新しいリストを作るための内包表記を記述してください。(例: [x ... for x in numbers])",
                "answer": "[x**2 for x in numbers]",
            },
            {
                "type": "fill_in",
                "question": "クラスのインスタンスが作成されるときに、初期化のために自動的に呼び出されるメソッドは何ですか？ (アンダースコア4つで囲む)",
                "answer": "__init__",
            },
        ]
    },
    "IT言語基礎": {
        "初級": [
            {
                "type": "choice",
                "question": "コンピュータの頭脳に相当する、中央処理装置をアルファベット3文字で何と呼びますか？",
                "choices": ["1. GPU", "2. RAM", "3. CPU"],
                "correct_choice_index": 2,
            },
            {
                "type": "choice",
                "question": "Webページを作成するために使われる、基本的なマークアップ言語は何ですか？",
                "choices": ["1. HTML", "2. CSS", "3. Python"],
                "correct_choice_index": 0,
            },
            {
                "type": "fill_in",
                "question": "インターネット上でコンピュータを識別するための、数字で構成された住所のようなものを何と呼びますか？ (○○アドレス)",
                "answer": "IP",
            },
        ],
        "中級": [
            {
                "type": "choice",
                "question": "WebブラウザとWebサーバ間でデータをやり取りする際に使われる、主要なプロトコルは何ですか？",
                "choices": ["1. FTP", "2. HTTP", "3. SMTP"],
                "correct_choice_index": 1,
            },
            {
                "type": "fill_in",
                "question": "データベースを操作するための問い合わせ言語で、データの検索や更新に広く使われているものは何ですか？ (アルファベット3文字)",
                "answer": "SQL",
            },
            {
                "type": "fill_in",
                "question": "DNSが担う主な役割は、ドメイン名と何を相互に変換することですか？ (○○アドレス)",
                "answer": "IP",
            },
        ]
    }
}


class QuizApp(tk.Tk):
    """アプリケーション全体を管理するメインクラス"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title(GAME_TITLE)
        self.geometry("600x450")
        self.minsize(500, 400)

        # フォントオブジェクトを定義
        self.title_font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE_L, weight="bold")
        self.question_font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE_M)
        self.result_font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE_L, weight="bold")
        self.default_font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE_M)
        self.small_font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE_S)
        
        # --- 変更点: ttkウィジェットのスタイルを設定 ---
        # これにより、OptionMenu (選択ボックス) の見た目を変更する
        style = ttk.Style(self)
        style.configure("TMenubutton", font=self.default_font, padding=5)


        # クイズの状態を管理
        self.selected_quiz_data = []
        self.current_quiz_index = 0
        self.wrong_answer_count = 0 

        self._frame = None
        self.switch_frame("SelectionFrame") # 最初に表示するフレームを変更

    def switch_frame(self, frame_class_name, **kwargs):
        """指定された名前のフレームに切り替える"""
        self.unbind_all_keys()
        if self._frame:
            self._frame.destroy()
        
        FrameClass = globals()[frame_class_name]
        self._frame = FrameClass(master=self, controller=self, **kwargs)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

    def unbind_all_keys(self):
        """キー入力の衝突を避けるため、既存のキーバインドを全て解除する"""
        self.unbind("<Return>")
        for i in range(1, 10):
            self.unbind(f"<KeyPress-{i}>")

    def start_quiz(self, genre, difficulty):
        """選択されたクイズを開始する"""
        self.selected_quiz_data = ALL_QUIZZES[genre][difficulty]
        self.current_quiz_index = 0
        self.wrong_answer_count = 0
        self.switch_frame("QuizFrame")

    def next_question(self):
        """次の問題に進むか、最終結果を表示する"""
        self.current_quiz_index += 1
        if self.current_quiz_index < len(self.selected_quiz_data):
            self.switch_frame("QuizFrame")
        else:
            self.switch_frame("FinalResultFrame")
            
    def record_wrong_answer(self):
        """不正解の数をカウント"""
        self.wrong_answer_count += 1


class SelectionFrame(tk.Frame):
    """ジャンルと難易度を選択する画面"""
    def __init__(self, master, controller, **kwargs):
        super().__init__(master)
        self.controller = controller
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(4, weight=1)

        title_label = tk.Label(self, text="クイズのジャンルを選択", font=controller.title_font)
        title_label.grid(row=0, column=0, columnspan=2, pady=20)

        # ジャンル選択
        genre_label = tk.Label(self, text="ジャンル:", font=controller.default_font)
        genre_label.grid(row=1, column=0, padx=(0, 10), pady=10, sticky="e")
        
        self.genre_var = tk.StringVar()
        self.genres = list(ALL_QUIZZES.keys())
        genre_menu = ttk.OptionMenu(self, self.genre_var, self.genres[0], *self.genres, command=self.update_difficulty_menu)
        # genre_menu.config(width=25)  # <- 変更点: 固定幅の設定を削除
        genre_menu.grid(row=1, column=1, pady=10, sticky="w")

        # 難易度選択
        difficulty_label = tk.Label(self, text="難易度:", font=controller.default_font)
        difficulty_label.grid(row=2, column=0, padx=(0, 10), pady=10, sticky="e")
        
        self.difficulty_var = tk.StringVar()
        self.difficulty_menu = ttk.OptionMenu(self, self.difficulty_var, "")
        # self.difficulty_menu.config(width=25) # <- 変更点: 固定幅の設定を削除
        self.difficulty_menu.grid(row=2, column=1, pady=10, sticky="w")
        
        # スタートボタン
        start_button = tk.Button(self, text="スタート", font=controller.default_font, width=15, command=self.start_quiz)
        start_button.grid(row=3, column=0, columnspan=2, pady=30)
        
        # 初期状態で難易度メニューを更新
        self.update_difficulty_menu()

    def update_difficulty_menu(self, event=None):
        """ジャンルの選択に応じて難易度メニューを更新する"""
        selected_genre = self.genre_var.get()
        difficulties = list(ALL_QUIZZES[selected_genre].keys())
        
        menu = self.difficulty_menu["menu"]
        menu.delete(0, "end")
        
        for difficulty in difficulties:
            menu.add_command(label=difficulty, command=lambda value=difficulty: self.difficulty_var.set(value))
            
        self.difficulty_var.set(difficulties[0])

    def start_quiz(self):
        """選択された設定でクイズを開始する"""
        genre = self.genre_var.get()
        difficulty = self.difficulty_var.get()
        if genre and difficulty:
            self.controller.start_quiz(genre, difficulty)


class QuizFrame(tk.Frame):
    """クイズ画面"""
    def __init__(self, master, controller, **kwargs):
        super().__init__(master)
        self.controller = controller
        self.grid_columnconfigure(0, weight=1)

        # controllerから選択されたクイズデータを取得
        quiz = self.controller.selected_quiz_data[controller.current_quiz_index]
        
        question_label = tk.Label(self, text=quiz["question"], font=controller.question_font, 
                                   wraplength=450, justify="left")
        question_label.grid(row=0, column=0, pady=20, sticky="w")

        if quiz["type"] == "choice":
            for i, choice in enumerate(quiz["choices"]):
                btn = tk.Button(self, text=choice, font=controller.default_font, 
                                command=lambda choice_idx=i: self.check_choice_answer(choice_idx))
                btn.grid(row=i+1, column=0, pady=5, sticky="ew")
                self.controller.bind(f"<KeyPress-{i+1}>", lambda event, choice_idx=i: self.check_choice_answer(choice_idx))
        else: # "fill_in"
            input_frame = tk.Frame(self)
            input_frame.grid(row=1, column=0, pady=20, sticky="ew")
            input_frame.grid_columnconfigure(1, weight=1)
            
            answer_label = tk.Label(input_frame, text="こたえ:", font=controller.default_font)
            answer_label.grid(row=0, column=0)
            
            self.entry = tk.Entry(input_frame, font=controller.default_font)
            self.entry.grid(row=0, column=1, padx=10, sticky="ew")
            self.entry.bind("<Return>", self.check_fill_in_answer)
            self.entry.focus_set()

            submit_button = tk.Button(self, text="決定", font=controller.default_font, command=self.check_fill_in_answer)
            submit_button.grid(row=2, column=0, pady=10)

    def check_choice_answer(self, choice_index):
        quiz = self.controller.selected_quiz_data[self.controller.current_quiz_index]
        is_correct = (choice_index == quiz["correct_choice_index"])
        if not is_correct:
            self.controller.record_wrong_answer()
        
        result_info = {
            "is_correct": is_correct,
            "player_answer": quiz["choices"][choice_index],
            "correct_answer_text": f'せいかいは: {quiz["choices"][quiz["correct_choice_index"]]}'
        }
        self.controller.switch_frame("ResultFrame", result_info=result_info)
        
    def check_fill_in_answer(self, event=None):
        player_answer = self.entry.get()
        if not player_answer:
            return

        quiz = self.controller.selected_quiz_data[self.controller.current_quiz_index]
        # 大文字小文字、前後の空白を無視して比較
        is_correct = (player_answer.lower().strip() == quiz["answer"].lower().strip())
        if not is_correct:
            self.controller.record_wrong_answer()

        result_info = {
            "is_correct": is_correct,
            "player_answer": player_answer,
            "correct_answer_text": f'せいかいは: {quiz["answer"]}'
        }
        self.controller.switch_frame("ResultFrame", result_info=result_info)

class ResultFrame(tk.Frame):
    """各問題の結果表示画面"""
    def __init__(self, master, controller, result_info, **kwargs):
        super().__init__(master)
        self.controller = controller
        self.grid_rowconfigure((0, 4), weight=1)
        self.grid_columnconfigure(0, weight=1)

        result_msg, result_color = ("正解！", "green") if result_info["is_correct"] else (" ざんねん…", "red")
            
        result_label = tk.Label(self, text=result_msg, font=controller.result_font, fg=result_color)
        result_label.grid(row=0, column=0, pady=20)
        
        answer_label = tk.Label(self, text=f"あなたの回答: {result_info['player_answer']}", font=controller.default_font)
        answer_label.grid(row=1, column=0, pady=10)
        
        if not result_info["is_correct"]:
            correct_label = tk.Label(self, text=result_info["correct_answer_text"], font=controller.default_font)
            correct_label.grid(row=2, column=0, pady=10)

        next_button = tk.Button(self, text="次へ", font=controller.default_font, width=15, command=controller.next_question)
        next_button.grid(row=3, column=0, pady=20)

        next_button.focus_set()
        self.controller.bind("<Return>", lambda event: self.controller.next_question())


class FinalResultFrame(tk.Frame):
    """全問終了後の最終結果画面"""
    def __init__(self, master, controller, **kwargs):
        super().__init__(master)
        self.controller = controller
        self.grid_rowconfigure((0, 4), weight=1)
        self.grid_columnconfigure(0, weight=1)

        total_questions = len(controller.selected_quiz_data)
        wrong_answers = controller.wrong_answer_count

        final_msg_label = tk.Label(self, text="クイズ終了！", font=controller.title_font)
        final_msg_label.grid(row=0, column=0, pady=20)

        score_text = f"全{total_questions}問中、不正解は {wrong_answers} 問でした。"
        score_label = tk.Label(self, text=score_text, font=controller.question_font)
        score_label.grid(row=1, column=0, pady=10)

        # やり直すボタン
        retry_button = tk.Button(self, text="同じクイズをやり直す", font=controller.default_font, width=20, command=self.retry_quiz)
        retry_button.grid(row=2, column=0, pady=10)

        # ジャンル選択に戻るボタン
        back_to_selection_button = tk.Button(self, text="ジャンル選択に戻る", font=controller.default_font, width=20, command=lambda: controller.switch_frame("SelectionFrame"))
        back_to_selection_button.grid(row=3, column=0, pady=5)

        # FinalResultFrameクラス内（終了ボタンの部分を以下のように変更）

        exit_button = tk.Button(self, text="終了する", font=controller.default_font, width=15, command=self.run_pushup_program)
        exit_button.grid(row=4, column=0, pady=(20, 0))

    def run_pushup_program(self):
        """腕立てプログラムを実行して終了"""
        self.controller.destroy()  # GUIを閉じる
        subprocess.run(["python", "pushup_counter.py"])  # スクリプト実行


    def retry_quiz(self):
        """同じ設定でクイズをやり直す"""
        # controller内のクイズ状態をリセットしてQuizFrameに遷移する
        self.controller.current_quiz_index = 0
        self.controller.wrong_answer_count = 0
        self.controller.switch_frame("QuizFrame")


if __name__ == "__main__":
    app = QuizApp()
    app.mainloop()