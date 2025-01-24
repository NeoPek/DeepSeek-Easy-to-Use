import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from openai import OpenAI
import threading
import os
import json
from datetime import datetime
import re

# 历史记录配置
HISTORY_DIR = "chathistory"
CONFIG_FILE = os.path.join(HISTORY_DIR, "config.json")
os.makedirs(HISTORY_DIR, exist_ok=True)

client = OpenAI(api_key="<YOUR_API_KEY>", base_url="https://api.deepseek.com/v1")

#其他设置
PROMPT_TOPIC = '用户正在通过api发起一个新的对话，请根据用户的发言总结此次对话的主题，不要回答任何多余内容' 
#          prompt hack 啦
# ╭(￣▽￣)╯
#
class ChatApplication:
    def __init__(self, root):
        self.root = root
        self.current_conversation = None
        self.messages = []
        self.selected_file = None
        self.setup_ui()
        self.load_last_conversation()

    def setup_ui(self):
        # 初始界面
        self.start_frame = tk.Frame(self.root)
        self.setup_start_ui()
        
        # 聊天界面
        self.chat_frame = tk.Frame(self.root)
        self.setup_chat_ui()
        
        self.start_frame.pack(fill=tk.BOTH, expand=True)

    def setup_start_ui(self):

        self.root.title("DeepSeek Mini(Easy to use)")
        # 左侧按钮列
        button_frame = tk.Frame(self.start_frame)
        button_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        btn_new = tk.Button(button_frame, text="开始新对话", command=self.start_new_conversation)
        btn_continue = tk.Button(button_frame, text="继续对话", command=self.continue_conversation)
        btn_load = tk.Button(button_frame, text="读取对话", command=self.load_conversation)
        
        btn_new.pack(fill=tk.X, pady=2)
        btn_continue.pack(fill=tk.X, pady=2)
        btn_load.pack(fill=tk.X, pady=2)
        
        # 右侧文件列表
        file_frame = tk.Frame(self.start_frame)
        file_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=5, pady=5)
        
        self.file_list = tk.Listbox(file_frame, selectmode=tk.SINGLE)
        scrollbar = ttk.Scrollbar(file_frame, command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=scrollbar.set)
        
        self.file_list.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.file_list.bind('<<ListboxSelect>>', self.on_file_select)
        self.load_file_list()

    def setup_chat_ui(self):
        # 主聊天界面
        self.root.geometry("1200x600")
    
        # 修改1：配置chat_frame的网格布局权重
        self.chat_frame.grid_rowconfigure(0, weight=1)
        self.chat_frame.grid_rowconfigure(1, weight=0)  # 输入区域固定高度
        self.chat_frame.grid_columnconfigure(0, weight=1)

        # 分割面板
        self.paned_window = tk.PanedWindow(self.chat_frame, orient=tk.HORIZONTAL, sashwidth=5)
        self.paned_window.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # 修改2：调整左右面板布局
        # 左侧对话面板
        left_frame = tk.Frame(self.paned_window)
        left_frame.rowconfigure(0, weight=1)
        left_frame.columnconfigure(0, weight=1)
        self.chat_display = tk.Text(left_frame, wrap=tk.WORD, padx=10, pady=10)
        chat_scroll = ttk.Scrollbar(left_frame, command=self.chat_display.yview)
        self.chat_display.configure(yscrollcommand=chat_scroll.set)
        self.chat_display.grid(row=0, column=0, sticky="nsew")
        chat_scroll.grid(row=0, column=1, sticky="ns")
        self.paned_window.add(left_frame, minsize=200)

        # 右侧思维链面板
        right_frame = tk.Frame(self.paned_window)
        right_frame.rowconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)
        self.reasoning_display = tk.Text(right_frame, wrap=tk.WORD, padx=10, pady=10)
        reasoning_scroll = ttk.Scrollbar(right_frame, command=self.reasoning_display.yview)
        self.reasoning_display.configure(yscrollcommand=reasoning_scroll.set)
        self.reasoning_display.grid(row=0, column=0, sticky="nsew")
        reasoning_scroll.grid(row=0, column=1, sticky="ns")
        self.paned_window.add(right_frame, minsize=200)

        # 修改3：优化输入区域布局
        input_frame = tk.Frame(self.chat_frame)
        input_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # 配置列权重
        input_frame.columnconfigure(1, weight=1)  # 输入框所在列
        #input_frame.columnconfigure(0, weight=1)

        # 添加返回按钮
        return_btn = tk.Button(input_frame, text="保存并返回", command=self.return_to_start)
        return_btn.grid(row=0, column=0, padx=(0,5), sticky="w")

        self.user_entry = AutoHeightText(input_frame, wrap=tk.WORD)
        input_scroll = ttk.Scrollbar(input_frame, command=self.user_entry.yview)
        self.user_entry.configure(yscrollcommand=input_scroll.set)

        send_button = tk.Button(input_frame, text="Send", command=self.send_message)
        modify_btn = tk.Button(input_frame, text="修改主题", command=self.modify_topic)

        # 调整组件布局
        self.user_entry.grid(row=0, column=1, sticky="nsew", padx=(0,5))
        input_scroll.grid(row=0, column=2, sticky="ns")
        modify_btn.grid(row=0, column=3, padx=5, sticky="e")
        send_button.grid(row=0, column=4, sticky="e")

        # 事件绑定
        self.user_entry.bind("<Return>", lambda e: (self.send_message(), "break")[1])
        self.user_entry.bind("<Shift-Return>", 
            lambda e: (
                self.user_entry.insert(tk.INSERT, "\n"),
                self.user_entry.see(tk.INSERT),
                self.user_entry._adjust_height(),
                "break"
            )[-1]
        )

    def load_file_list(self):
        self.file_list.delete(0, tk.END)
        files = os.listdir(HISTORY_DIR)
        json_files = [f for f in files if f.endswith('.json') and f != 'config.json']
        for f in sorted(json_files, key=lambda x: os.path.getctime(os.path.join(HISTORY_DIR, x)), reverse=True):
            self.file_list.insert(tk.END, f)

    def on_file_select(self, event):
        selection = self.file_list.curselection()
        if selection:
            self.selected_file = self.file_list.get(selection[0])

    def start_new_conversation(self):
        self.current_conversation = None
        self.messages = []
        self.switch_to_chat()
        self.clear_displays()

    def continue_conversation(self):
        if self.current_conversation:
            self.switch_to_chat()
            self.load_history_to_ui()
        else:
            messagebox.showinfo("提示", "没有最近的对话记录")

    def load_conversation(self):
        if self.selected_file:
            file_path = os.path.join(HISTORY_DIR, self.selected_file)
            self.current_conversation = file_path
            self.messages = self.load_history(file_path)
            self.update_config('last_conversation', file_path)
            self.switch_to_chat()
            self.load_history_to_ui()
        else:
            messagebox.showinfo("提示", "请先选择一个对话文件")

    def switch_to_chat(self):
        self.start_frame.pack_forget()
        self.chat_frame.pack(fill=tk.BOTH, expand=True)
        if self.current_conversation:
           filename = os.path.basename(self.current_conversation)
           self.root.title(f"DeepSeek Mini - {filename}")

    def return_to_start(self):
        self.save_conversation()
        self.switch_to_start()

    def switch_to_start(self):
        self.chat_frame.pack_forget()
        self.start_frame.pack(fill=tk.BOTH, expand=True)
        self.root.title("DeepSeek Mini (Easy to Use)")
        self.load_file_list()
        self.user_entry.delete("1.0", tk.END)

    def clear_displays(self):
        for display in [self.chat_display, self.reasoning_display]:
            display.config(state=tk.NORMAL)
            display.delete(1.0, tk.END)
            display.config(state=tk.DISABLED)

    def load_history(self, file_path):
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return [{**entry, 'content': re.sub(PROMPT_TOPIC, '', entry['content'])} for entry in json.load(f) if 'content' in entry]
        return []

    def load_history_to_ui(self):
        self.clear_displays()
        for msg in self.messages:
            if msg["role"] == "user":
                self.update_display(f"You:\n{msg['content']}\n", "left")
            elif msg["role"] == "assistant":
                self.update_display(f"Response({msg['timestamp']}):\n{msg['content']}\n", "left")
                self.update_display(f"Reasoning({msg['timestamp']}):\n{msg['reasoning']}\n", "right")

    def send_message(self):
        user_input = self.user_entry.get("1.0", tk.END).strip()
        if not user_input:
            return
        
        self.messages.append({
            "role": "user", 
            "content": user_input,
            "timestamp": datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        })
        self.save_conversation()

        self.update_display(f"You:\n{user_input}\n", "left")
        self.user_entry.delete("1.0", tk.END)
        self.user_entry.configure(height=self.user_entry.default_height)
        self.user_entry.focus_set()
        
        is_new_conversation = not self.current_conversation
        if is_new_conversation:
            timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            self.current_conversation = os.path.join(HISTORY_DIR, f"temp_{timestamp}.json")
            self.update_config('last_conversation', self.current_conversation)
            
            threading.Thread(target=self.stream_response, args=(self.messages.copy(), False)).start()
            threading.Thread(target=self.stream_response, args=([{"role": "user", "content": PROMPT_TOPIC}], True)).start()
        else:
            threading.Thread(target=self.stream_response, args=(self.messages.copy(), False)).start()

    def stream_response(self, messages, is_topic_extraction):
        response_content = ""
        reasoning_content = ""
        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

        try:
            stream = client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            stream=True  # 强制启用流式传输
        )

            if not is_topic_extraction:
                self.update_display(f"Response({timestamp}):\n", "left", streaming=True)
                self.update_display(f"Reasoning({timestamp}):\n", "right", streaming=True)

            for chunk in stream:
                delta = chunk.choices[0].delta
                
                if not is_topic_extraction:
                    # 处理推理内容
                    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                        new_reasoning = delta.reasoning_content
                        reasoning_content += new_reasoning
                        self.update_display(new_reasoning, "right", streaming=True)
                
                    # 处理主要响应内容
                    if hasattr(delta, "content") and delta.content:
                        new_content = delta.content
                        response_content += new_content
                        self.update_display(new_content, "left", streaming=True)
                else:
                    if hasattr(delta, "content") and delta.content:
                        new_content = delta.content
                        response_content += new_content

            if is_topic_extraction:
                self._handle_topic_change(response_content, timestamp)
                return

            #保存最终消息
            self.messages.append({
                "role": "assistant",
                "content": response_content,
                "reasoning": reasoning_content,
                "timestamp": timestamp
            })
            self.save_conversation()
            
            self.update_display("\n", "left", streaming=False)
            self.update_display("\n", "right", streaming=False)
            
        except Exception as e:
            self.messages.append({
                "role": "assistant",
                "content": "ERROR_IN_RESPONSE",
                "reasoning": "ERROR_IN_REASONING",
                "timestamp": timestamp
            })
            self.save_conversation()
            self.update_display(f"\nError: {str(e)}\n", "left", streaming=False)

    # 新增辅助方法
    def _handle_topic_change(self, topic, timestamp):
        new_filename = f"{topic}_{timestamp}.json"
        new_path = os.path.join(HISTORY_DIR, new_filename)
        
        if os.path.exists(self.current_conversation):
            os.rename(self.current_conversation, new_path)
        
        self.current_conversation = new_path
        self.update_config('last_conversation', new_path)
        self.root.title(f"DeepSeek Mini - {new_filename}")

    def update_display(self, text, position, streaming=False):
        target = self.chat_display if position == "left" else self.reasoning_display
        target.after(0, lambda: self._update_display(target, text, streaming))

    def _update_display(self, widget, text, streaming):
        widget.config(state=tk.NORMAL)
        widget.insert(tk.END, text)
        if not streaming:
            widget.insert(tk.END, "\n")
        widget.see(tk.END)
        widget.config(state=tk.DISABLED)

    def save_conversation(self):
        if self.current_conversation:
            with open(self.current_conversation, 'w', encoding='utf-8') as f:
                json.dump(self.messages, f, ensure_ascii=False, indent=2)

    def modify_topic(self):
        if not self.current_conversation:
            return
            
        new_topic = simpledialog.askstring("修改主题", "请输入新主题:")
        if new_topic:
            old_path = self.current_conversation
            dir_name = os.path.dirname(old_path)
            base_name = os.path.basename(old_path)
            parts = base_name.split('_')
            new_name = f"{new_topic}_{'_'.join(parts[1:])}"
            new_path = os.path.join(dir_name, new_name)
            
            try:
                os.rename(old_path, new_path)
                self.current_conversation = new_path
                self.update_config('last_conversation', new_path)
                self.load_file_list()
            except Exception as e:
                messagebox.showerror("错误", f"重命名失败: {str(e)}")

    def update_config(self, key, value):
        config = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        config[key] = value
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)

    def load_last_conversation(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                self.current_conversation = config.get('last_conversation')
                if self.current_conversation and os.path.exists(self.current_conversation):
                    self.messages = self.load_history(self.current_conversation)

class AutoHeightText(tk.Text):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_height = 3
        self.max_height = 8
        self.configure(height=self.default_height)
        self.bind("<Key>", self._schedule_adjust)
        self.bind("<FocusIn>", self._schedule_adjust)
        self.bind("<FocusOut>", self._schedule_adjust)
    
    def _schedule_adjust(self, event=None):
        self.after(50, self._adjust_height)
    
    def _adjust_height(self):
        line_count = int(self.index("end-1c").split('.')[0])
        new_height = min(max(line_count, self.default_height), self.max_height)
        self.configure(height=new_height)

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApplication(root)
    root.mainloop()