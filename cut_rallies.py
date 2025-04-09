import cv2
import tkinter as tk
from tkinter import filedialog, ttk
import csv
import os
import numpy as np
from PIL import Image, ImageTk
import datetime

class RallyCutterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Rally Cutter Tool")
        self.root.geometry("1600x1000")
        
        # 視頻變量
        self.video_path = None
        self.cap = None
        self.total_frames = 0
        self.fps = 0
        self.current_frame = 0
        self.play_status = False
        self.rally_markers = []  # 存儲格式: [{'start_frame': x, 'end_frame': y, 'start_time': 'xx:xx:xx', 'end_time': 'xx:xx:xx'}]
        self.current_rally = None  # 當前正在標記的回合
        self.video_width = 1600  # 默認視頻寬度
        self.video_height = 1200  # 默認視頻高度
        
        # 創建UI組件
        self.create_ui()
        
        # 綁定鍵盤事件
        self.root.bind('<KeyPress>', self.key_press_event)
        
        # 綁定窗口大小變化事件
        self.root.bind('<Configure>', self.on_window_resize)
        
        # 更新状态
        self.update_status("歡迎使用Rally切割工具。請加載視頻文件開始。")
        
    def create_ui(self):
        # 主布局
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 使用 grid 佈局
        main_frame.grid_rowconfigure(0, weight=0)  # 控制區 (固定高度)
        main_frame.grid_rowconfigure(1, weight=10)  # video 區 (可擴展)
        main_frame.grid_rowconfigure(2, weight=0)  # 進度條 (固定高度)
        main_frame.grid_rowconfigure(3, weight=0)  # 時間顯示 (固定高度)
        main_frame.grid_rowconfigure(4, weight=0)  # 回合標記 (固定高度，可調整)
        main_frame.grid_rowconfigure(5, weight=0)  # 快捷鍵說明 (固定高度)
        main_frame.grid_rowconfigure(6, weight=0)  # 狀態欄 (固定高度)
        main_frame.grid_columnconfigure(0, weight=1)  # 單列，水平擴展
        
        # 頂部控制區
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=0, column=0, sticky="ew", pady=5)
        
        # 加載視頻按鈕
        load_btn = ttk.Button(control_frame, text="加載影片", command=self.load_video)
        load_btn.pack(side=tk.LEFT, padx=5)
        
        # 導出CSV按鈕
        export_btn = ttk.Button(control_frame, text="導出CSV (E)", command=self.export_csv)
        export_btn.pack(side=tk.LEFT, padx=5)
        
        # 播放/暫停按鈕
        self.play_btn = ttk.Button(control_frame, text="播放 (P)", command=self.toggle_play)
        self.play_btn.pack(side=tk.LEFT, padx=5)
        
        # 刪除最後標記按鈕
        delete_btn = ttk.Button(control_frame, text="刪除最後標記 (BackSpace)", command=self.delete_last_marker)
        delete_btn.pack(side=tk.LEFT, padx=5)
        
        # 標記按鈕
        self.mark_btn = ttk.Button(control_frame, text="標記回合開始 (S)", command=self.start_marker)
        self.mark_btn.pack(side=tk.LEFT, padx=5)
        
        # 標記按鈕
        self.mark_btn = ttk.Button(control_frame, text="標記回合結束 (D)", command=self.end_marker)
        self.mark_btn.pack(side=tk.LEFT, padx=5)
        
        # Video 區域
        self.video_frame = ttk.Frame(main_frame, borderwidth=2, relief="groove")
        self.video_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        
        # Video 顯示標籤
        self.video_label = ttk.Label(self.video_frame)
        self.video_label.pack(fill=tk.BOTH, expand=True)
        
        # 進度條
        progress_frame = ttk.Frame(main_frame)
        progress_frame.grid(row=2, column=0, sticky="ew", pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Scale(
            progress_frame, 
            from_=0, 
            to=100, 
            orient=tk.HORIZONTAL, 
            variable=self.progress_var,
            command=self.on_progress_change
        )
        self.progress_bar.pack(fill=tk.X, padx=5)
        
        # 時間顯示
        time_frame = ttk.Frame(main_frame)
        time_frame.grid(row=3, column=0, sticky="ew", pady=5)

        self.time_label = ttk.Label(time_frame, text="00:00:00 / 00:00:00")
        self.time_label.pack(side=tk.LEFT)

        self.frame_label = ttk.Label(time_frame, text="Frame: 0 / 0")
        self.frame_label.pack(side=tk.RIGHT)
        
        # 回合標記列表
        markers_frame = ttk.LabelFrame(main_frame, text="回合標記")
        markers_frame.grid(row=4, column=0, sticky="ew", pady=5, ipady=5)

        # 創建表格
        columns = ('num', 'start_time', 'end_time', 'duration', 'start_frame', 'end_frame')
        self.marker_tree = ttk.Treeview(markers_frame, columns=columns, show='headings')
        
        # 設置 Header
        self.marker_tree.heading('num', text='#')
        self.marker_tree.heading('start_time', text='開始時間')
        self.marker_tree.heading('end_time', text='結束時間')
        self.marker_tree.heading('duration', text='持續時間')
        self.marker_tree.heading('start_frame', text='開始幀')
        self.marker_tree.heading('end_frame', text='結束幀')
        
        # 設置列寬
        self.marker_tree.column('num', width=50)
        self.marker_tree.column('start_time', width=150)
        self.marker_tree.column('end_time', width=150)
        self.marker_tree.column('duration', width=100)
        self.marker_tree.column('start_frame', width=100)
        self.marker_tree.column('end_frame', width=100)
        
        # 添加 Slider
        marker_scroll = ttk.Scrollbar(markers_frame, orient=tk.VERTICAL, command=self.marker_tree.yview)
        self.marker_tree.configure(yscrollcommand=marker_scroll.set)
        
        # 放置表格和 Slider
        self.marker_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        marker_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 快捷鍵幫助框
        help_frame = ttk.LabelFrame(main_frame, text="快捷鍵說明")
        help_frame.grid(row=5, column=0, sticky="ew", pady=5, ipady=5)

        help_text = """
        S 鍵: 標記回合開始
        D 鍵: 標記回合結束
        P 鍵: 播放/暫停
        E 鍵: 導出CSV
        →: 前進1幀
        ←: 後退1幀
        ↑: 前進10幀
        ↓: 後退10幀
        P: 播放/暫停
        Backspace: 刪除最後標記
        """
        help_label = ttk.Label(help_frame, text=help_text)
        help_label.pack(padx=5, pady=5)
        
        # 狀態欄
        self.status_var = tk.StringVar()
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=6, column=0, sticky="ew", pady=5)

        # 更新初始狀態
        self.update_status("歡迎使用Rally切割工具。請加載影片。")
        
    def on_window_resize(self, event):
        if event.widget == self.root:
            # 更新顯示尺寸
            self.display_width = max(1, self.video_frame.winfo_width())
            self.display_height = max(1, self.video_frame.winfo_height())
            
            if self.cap is not None and self.current_frame >= 0:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
                ret, frame = self.cap.read()
                if ret:
                    self.display_frame(frame)
    
    def load_video(self):
        file_path = filedialog.askopenfilename(
            title="選擇視頻文件",
            filetypes=(("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*"))
        )
        
        if not file_path:
            return
            
        # 重置所有狀態
        self.video_path = file_path
        self.rally_markers = []
        self.current_rally = None
        self.current_frame = 0
        self.play_status = False
        # self.mark_btn.configure(text="標記回合開始")
        
        
        # 清空表格
        for i in self.marker_tree.get_children():
            self.marker_tree.delete(i)
            
        # 打開視頻
        self.cap = cv2.VideoCapture(file_path)
        if not self.cap.isOpened():
            self.update_status("無法打開視頻文件")
            return
            
        # 獲取視頻信息
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.video_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # 設定固定的顯示尺寸（初始值）
        self.display_width = 800
        self.display_height = 600
        
        # 更新進度條
        self.progress_bar.configure(to=self.total_frames-1)
        
        # 更新狀態
        video_name = os.path.basename(file_path)
        self.update_status(f"已加載視頻: {video_name} ({self.video_width}x{self.video_height}, {self.fps:.2f} FPS, {self.total_frames} 幀)")
        
        # 顯示第一幀
        self.seek_frame(0)
        self.update_time_display()
            
    def toggle_play(self):
        self.play_status = not self.play_status
        
        if self.play_status:
            self.play_btn.configure(text="暫停")
            self.play_video()
        else:
            self.play_btn.configure(text="播放")
            
    def play_video(self):
        if self.cap is None or not self.play_status:
            return
            
        # 如果已經到達最後一幀，循環回第一幀
        if self.current_frame >= self.total_frames - 1:
            self.current_frame = 0
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
        ret, frame = self.cap.read()
        
        if ret:
            self.current_frame += 1
            self.display_frame(frame)
            self.progress_var.set(self.current_frame)
            self.update_time_display()
            
            # 30毫秒後繼續顯示下一幀 (大約33 FPS)
            self.root.after(30, self.play_video)
        else:
            self.play_status = False
            self.play_btn.configure(text="播放")
            
    def seek_frame(self, frame_num):
        if self.cap is None:
            return
            
        # 確保幀數在有效範圍內
        frame_num = max(0, min(frame_num, self.total_frames - 1))
        
        # 設置視頻位置
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = self.cap.read()
        
        if ret:
            self.current_frame = frame_num
            self.display_frame(frame)
            self.progress_var.set(self.current_frame)
            self.update_time_display()
            
    def step_frames(self, step):
        if self.cap is None:
            return
            
        target_frame = self.current_frame + step
        self.seek_frame(target_frame)
            
    def on_progress_change(self, value):
        if self.cap is None:
            return
            
        frame_num = int(float(value))
        if frame_num != self.current_frame:
            self.seek_frame(frame_num)
            
    def display_frame(self, frame):
        if frame is None:
            return
            
        # 轉換顏色空間從BGR到RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 動態獲取顯示區域大小
        self.display_width = max(1, self.video_frame.winfo_width())
        self.display_height = max(1, self.video_frame.winfo_height())
        
        # 計算縮放比例，保持寬高比
        frame_h, frame_w = frame_rgb.shape[:2]
        scale = min(self.display_width / frame_w, self.display_height / frame_h)
        new_w, new_h = int(frame_w * scale), int(frame_h * scale)
        frame_rgb = cv2.resize(frame_rgb, (new_w, new_h))
        
        # 如果縮放後的圖像小於顯示區域，居中顯示
        if new_w < self.display_width or new_h < self.display_height:
            canvas = np.zeros((self.display_height, self.display_width, 3), dtype=np.uint8)
            x_offset = (self.display_width - new_w) // 2
            y_offset = (self.display_height - new_h) // 2
            canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = frame_rgb
            frame_rgb = canvas
        
        img = Image.fromarray(frame_rgb)
        img_tk = ImageTk.PhotoImage(image=img)
        
        self.video_label.configure(image=None)
        self.video_label.configure(image=img_tk)
        self.video_label.image = img_tk
        
    def update_time_display(self):
        if self.cap is None:
            return
            
        # 計算當前時間和總時間
        current_time = self.frame_to_time(self.current_frame)
        total_time = self.frame_to_time(self.total_frames)
        
        # 更新時間顯示
        self.time_label.configure(text=f"{current_time} / {total_time}")
        self.frame_label.configure(text=f"Frame: {self.current_frame} / {self.total_frames}")
        
    def frame_to_time(self, frame_num):
        if self.fps <= 0:
            return "00:00:00"
            
        total_seconds = frame_num / self.fps
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int((total_seconds * 1000) % 1000)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        
    def start_marker(self):
        if self.cap is None:
            return
            
        if self.current_rally is not None:
            self.update_status("已有未完成的回合標記，請先結束當前回合")
            return

        current_time = self.frame_to_time(self.current_frame)
        self.current_rally = {
            'start_frame': self.current_frame,
            'start_time': current_time,
            'end_frame': None,
            'end_time': None
        }
        self.mark_btn.configure(text="標記回合結束 (D)")
        self.update_status(f"已標記回合 #{len(self.rally_markers) + 1} 開始於 {current_time} (幀 {self.current_frame})")

    def end_marker(self):
        if self.cap is None:
            return
            
        if self.current_rally is None:
            self.update_status("請先標記回合開始")
            return

        current_time = self.frame_to_time(self.current_frame)
        if self.current_frame <= self.current_rally['start_frame']:
            self.update_status("錯誤: 結束幀必須在開始幀之後")
            return

        self.current_rally['end_frame'] = self.current_frame
        self.current_rally['end_time'] = current_time

        # 添加到標記列表
        self.rally_markers.append(self.current_rally)

        # 計算持續時間
        start_seconds = self.current_rally['start_frame'] / self.fps
        end_seconds = self.current_frame / self.fps
        duration = self.format_duration(end_seconds - start_seconds)

        # 添加到表格
        self.marker_tree.insert(
            '', 'end',
            values=(
                len(self.rally_markers),
                self.current_rally['start_time'],
                self.current_rally['end_time'],
                duration,
                self.current_rally['start_frame'],
                self.current_frame
            )
        )

        self.current_rally = None
        self.mark_btn.configure(text="標記回合開始")
        self.update_status(f"已標記回合 #{len(self.rally_markers)} 結束於 {current_time} (幀 {self.current_frame})")      
    def format_duration(self, seconds):
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        ms = int((seconds * 1000) % 1000)
        return f"{minutes:02d}:{secs:02d}.{ms:03d}"
        
    def delete_last_marker(self):
        if self.current_rally is not None:
            # 取消當前未完成的標記
            self.current_rally = None
            self.mark_btn.configure(text="標記回合開始 (S)")
            self.update_status("已取消當前回合標記")
        elif self.rally_markers:
            # 刪除最後一個完整標記
            self.rally_markers.pop()
            
            # 從表格中刪除
            items = self.marker_tree.get_children()
            if items:
                self.marker_tree.delete(items[-1])
                
            self.update_status(f"已刪除最後一個回合標記，剩餘 {len(self.rally_markers)} 個標記")
            
    def export_csv(self):
        if not self.rally_markers:
            self.update_status("沒有回合標記可以導出")
            return
            
        file_path = filedialog.asksaveasfilename(
            title="保存CSV文件",
            defaultextension=".csv",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*"))
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # 寫入標題行
                writer.writerow([
                    'Rally Number', 
                    'Start Time', 
                    'End Time', 
                    'Duration', 
                    'Start Frame',
                    'End Frame',
                    'Start Seconds',
                    'End Seconds'
                ])
                
                # 寫入數據行
                for i, marker in enumerate(self.rally_markers):
                    start_seconds = marker['start_frame'] / self.fps
                    end_seconds = marker['end_frame'] / self.fps
                    duration = end_seconds - start_seconds
                    
                    writer.writerow([
                        i + 1,
                        marker['start_time'],
                        marker['end_time'],
                        self.format_duration(duration),
                        marker['start_frame'],
                        marker['end_frame'],
                        f"{start_seconds:.3f}",
                        f"{end_seconds:.3f}"
                    ])
                    
            self.update_status(f"已成功導出CSV文件到 {file_path}")
        except Exception as e:
            self.update_status(f"導出CSV時出錯: {str(e)}")
            
    def key_press_event(self, event):
        if self.cap is None:
            return
            
        # 控制鍵
        if event.keysym == 's' or event.keysym == 'S':  # S 鍵開始標記
            self.start_marker()
        elif event.keysym == 'd' or event.keysym == 'D':  # D 鍵結束標記
            self.end_marker()
        elif event.keysym == 'p' or event.keysym == 'P':
            self.toggle_play()
        elif event.keysym == 'BackSpace':
            self.delete_last_marker()
        elif event.keysym == 'e' or event.keysym == 'E': # 導出CSV
            self.export_csv()
        elif event.keysym == 'Right':
            self.step_frames(1)  # 前進1幀
        elif event.keysym == 'Left':
            self.step_frames(-1)  # 後退1幀
        elif event.keysym == 'Up':
            self.step_frames(10)  # 前進10幀
        elif event.keysym == 'Down':
            self.step_frames(-10)  # 後退10幀
            
    def update_status(self, message):
        self.status_var.set(message)
        print(message)  # 同時在控制台打印
        
    def close(self):
        if self.cap is not None:
            self.cap.release()
            

# 啟動應用程序
def main():
    root = tk.Tk()
    app = RallyCutterApp(root)
    
    # 設置關閉窗口時的回調
    root.protocol("WM_DELETE_WINDOW", lambda: (app.close(), root.destroy()))
    
    root.mainloop()

if __name__ == "__main__":
    main()
