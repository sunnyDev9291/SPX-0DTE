
import sys
from datetime import datetime, timedelta
from timeit import Timer
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QGridLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QFrame, QDialog, QRadioButton)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, QTimer, QDateTime, QPoint,pyqtSignal, QObject,QThread
import asyncio
from datetime import datetime, timedelta

import platform
from ib_insync import IB, Option, Index, MarketOrder, ComboLeg, Contract, LimitOrder, OrderStatus
import time
import pandas as pd
import threading
import numpy
import bisect
#second




connected = False

ib = IB()
buy_option_contract = None
sell_option_contract = None
sell_option_detail = None
buy_option_detail = None


if platform.system() == 'Windows':
    # pass
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class PriceUpdateSignal(QObject):
    spx_price_updated = pyqtSignal(float)
    vix_price_updated = pyqtSignal(float)
    yesterday_close = pyqtSignal(float)
    ema_spx = pyqtSignal(float)
    buy_strike_price = pyqtSignal(int)
    sell_strike_price = pyqtSignal(int)
    buy_option_updated = pyqtSignal(tuple)
    sell_option_updated = pyqtSignal(tuple)



class TwoRadioDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Where are you going to trade?")
        self.resize(300, 150)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        # Remove help button if possible (commented out if not available)
        # self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        # Apply black beautiful style
        self.setStyleSheet('''
            QDialog {
                background-color: #23272A;
                color: #EAECEE;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
            }
            QRadioButton {
                color: #EAECEE;
                font-size: 14px;
                spacing: 10px;
            }
            QRadioButton::indicator:checked {
                background-color: #43B581;
                border: 1px solid #43B581;
            }
            QRadioButton::indicator:unchecked {
                background-color: #2C2F33;
                border: 1px solid #40444B;
            }
            QPushButton {
                background-color: #5865F2;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #4A54C9;
            }
        ''')
        layout = QVBoxLayout(self)

        self.radio1 = QRadioButton("In Live account")
        self.radio2 = QRadioButton("In Paper account")
        self.radio1.setChecked(True)  # Default selection

        layout.addWidget(self.radio1)
        layout.addWidget(self.radio2)

        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.accept)
        layout.addWidget(self.ok_btn)

    def selected_option(self):
        if self.radio1.isChecked():
            return 1
        elif self.radio2.isChecked():
            return 2


class WaitingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Please wait")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        layout = QVBoxLayout(self)
        label = QLabel("Loading...", self)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self.setFixedSize(300, 40)
        


class TradingAppQt(QWidget):
    def __init__(self):
        super().__init__()
        self.old_pos = None
        self.ordered_trade = None
        self.init_ui()
        self.signals = PriceUpdateSignal()
        self.signals.spx_price_updated.connect(self.update_spx)
        self.signals.vix_price_updated.connect(self.update_vix)
        self.signals.yesterday_close.connect(self.show_yesterday_close)
        self.signals.ema_spx.connect(self.show_ema_spx)
        self.signals.buy_strike_price.connect(self.update_buy_strike_price)
        self.signals.sell_strike_price.connect(self.update_sell_strike_price)
        
        self.signals.buy_option_updated.connect(self.buy_option_update)
        self.signals.sell_option_updated.connect(self.sell_option_update)

    def show_yesterday_close(self,price):
        # print("yesterday_closing_price", price)
        self.yesterday_vix_value_label.setText(f"{price:.2f}")

    def show_ema_spx(self,price):
        # print("ema_price", price)
        self.spx_ema_value_label.setText(f"{price:.2f}")

    def update_spx(self, price):
        # self.spx_label.setText(f"SPX Price: {price}")
        # print("spx : ",price)
        self.current_spx_value_label.setText(f"{price:.2f}")
        if self.spx_ema_value_label.text() != " " and hasattr(self, 'trade_flag1'):
            if float(self.current_spx_value_label.text()) > float(self.spx_ema_value_label.text()) and self.trade_flag1 == True:
                self.trading_flag_label.setText("Trading flag : <b style='color:#43B581;'>Please trade</b>")
            else:
                self.trading_flag_label.setText("Trading flag : <b style='color:#ED4245;'>Don't trade</b>")
            


    def update_vix(self, price):
        # print("vix : ", price)
        self.current_vix_value_label.setText(f"{price:.2f}")
        if price < float(self.yesterday_vix_value_label.text()):
            self.trade_flag1 = True
        else:
            self.trade_flag1 = False
        


    def update_buy_strike_price(self,price):
        # print("buy strike price : ", price)
        self.buy_labels[1].setText(f"{price:.2f}")
    
    def update_sell_strike_price(self,price):
        # print("sell strike price : ", price)
        self.sell_labels[1].setText(f"{price:.2f}")

    def buy_option_update(self,ticker):
        # print(f"buy info : bid : {ticker[0]},ask : {ticker[1]}")
        self.buy_labels[2].setText(f"{ticker[0]:.2f}")
        self.buy_labels[3].setText(f"{ticker[1]:.2f}")
        try:
            spread_bid = ticker[0] - float(self.sell_labels[3].text())
            self.call_spread_labels[2].setText(f"{spread_bid:.2f}")

            spread_ask = ticker[1] - float(self.sell_labels[2].text())
            self.call_spread_labels[3].setText(f"{spread_ask:.2f}")

            arr = numpy.arange(spread_bid, spread_ask+0.05, 0.05)
            mid_index = 0
            if len(arr)%2 != 0:
                mid_index = len(arr) // 2
            else:
                mid_index = len(arr) //2 - 1 
            self.midpoint = midpoint = round(arr[mid_index],2)
            self.current_net_price_label.setText(f"Midpoint price : {self.midpoint}")

        except Exception as e:
            pass
        

    def sell_option_update(self,ticker):
        # print(f"sell info : bid : {ticker[0]},ask : {ticker[1]}")
        self.sell_labels[2].setText(f"{ticker[0]:.2f}")
        self.sell_labels[3].setText(f"{ticker[1]:.2f}")

        try:
            spread_bid = float(self.buy_labels[2].text()) - ticker[1]
            self.call_spread_labels[2].setText(f"{spread_bid:.2f}")

            spread_ask = float(self.buy_labels[3].text()) - ticker[0]
            self.call_spread_labels[3].setText(f"{spread_ask:.2f}")

            arr = numpy.arange(spread_bid, spread_ask+0.050, 0.05)
            mid_index = 0
            if len(arr) % 2 != 0:
                mid_index = len(arr) // 2
            else:
                mid_index = len(arr) // 2 - 1   
            self.midpoint = midpoint = round(arr[mid_index],2)
            self.current_net_price_label.setText(f"Midpoint price : {self.midpoint}")
        except Exception as e:
            pass



    def init_ui(self):
        global connected
        print(connected)
        # self.setWindowTitle("Trading Bot")
        self.setGeometry(100, 100, 800, 820)
        self.setWindowOpacity(0.9)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        
        # --- Centralized Stylesheet (QSS) for a beautiful black theme ---
        stylesheet = """
            QWidget {
                background-color: #23272A;
                font-family: 'Segoe UI', sans-serif;
                color: #EAECEE;
            }
            QFrame#title_bar {
                background-color: #2C2F33;
            }
            QLabel#title_text {
                font-size: 14px;
                font-weight: bold;
                color: #FFFFFF;
                padding-left: 10px;
            }
            QPushButton#close_button {
                background-color: transparent;
                border: none;
                font-family: 'Arial', 'sans-serif';
                font-size: 22px;
                font-weight: bold;
                color: #99AAB5;
            }
            QPushButton#close_button:hover {
                background-color: #ED4245;
                color: white;
            }
            QFrame#bordered_frame {
                background-color: #2C2F33;
                border: 1px solid #40444B;
                border-radius: 6px;
            }
            QLineEdit {
                background-color: #40444B;
                border: 1px solid #1E1F22;
                border-radius: 4px;
                padding: 5px;
                font-size: 14px;
                color: #EAECEE;
            }
            QLineEdit:focus {
                border: 1px solid #5865F2;
            }
            QPushButton#start_button {
                background-color: #43B581;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 5px;
            }
            QPushButton#start_button:hover {
                background-color: #3AA571;
            }
            QPushButton#start_button:pressed {
                background-color: #2e8c5a;
            }
            QPushButton#start_button:disabled {
                background-color: #888;
                color: #eee;
            }
            QPushButton#stop_button {
                background-color: #ED4245;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 5px;
            }
            QPushButton#stop_button:hover {
                background-color: #D63B3E;
            }
            QPushButton#stop_button:pressed {
                background-color: #a82c2e;
            }
            QPushButton#stop_button:disabled {
                background-color: #888;
                color: #eee;
            }
            QPushButton#change_button {
                background-color: #5865F2;
                color: white;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 5px;
            }
            QPushButton#change_button:hover {
                background-color: #4A54C9;
            }
        """
        self.setStyleSheet(stylesheet)

        # Main vertical layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- Custom Title Bar ---
        self.title_bar = QFrame(self)
        self.title_bar.setObjectName("title_bar")
        self.title_bar.setFixedHeight(40)
        title_bar_layout = QHBoxLayout(self.title_bar)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("Trading Bot", self)
        title_label.setObjectName("title_text")
        
        close_btn = QPushButton("✕", self)
        close_btn.setObjectName("close_button")
        close_btn.setFixedSize(45, 40)
        close_btn.clicked.connect(lambda: {self.close_application()})  # type: ignore

        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(close_btn)
        main_layout.addWidget(self.title_bar)

        # --- Main Content Area ---
        content_area = QFrame(self)
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(10)
        main_layout.addWidget(content_area)

        # --- Top Status Section ---
        top_frame = QFrame(self)
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(0, 0, 0, 0)
        status_text = "connected" if connected else "disconnected"
        status_color = "#43B581" if connected else "#ED4245"
        # self.api_status = QLabel(f"API Status : <b style='color:{status_color};'>{status_text}</b>", self)
        # self.api_status.setFont(QFont('Segoe UI', 14))
        
        self.current_time = QLabel(self)
        self.current_time.setFont(QFont('Segoe UI', 14))
        
        # top_layout.addWidget(self.api_status)
        top_layout.addStretch()
        top_layout.addWidget(self.current_time)
        content_layout.addWidget(top_frame)

        # --- Data Frame ---
        data_frame = QFrame(self)
        data_frame.setObjectName("bordered_frame")
        data_layout = QGridLayout(data_frame)
        data_layout.setSpacing(10)

        labels_data = [
            ("Current VIX : "   , " "),
            ("Yesterday VIX : " , " "),
            ("Current SPX : "   , " "),
            ("SPX EMA in 50 min", " ")
        ]

        for i, (text, value) in enumerate(labels_data):
            label_widget = QLabel(text, self)
            label_widget.setFont(QFont('Segoe UI', 14))
            if "SPX EMA" in text:
                self.spx_ema_label = label_widget

            data_layout.addWidget(label_widget, i, 0, Qt.AlignLeft)  # type: ignore
            
            value_label = QLabel(value, self)
            value_label.setFont(QFont('Segoe UI', 14))
            if "SPX EMA" in text:
                self.spx_ema_value_label = value_label
            data_layout.addWidget(value_label, i, 1, Qt.AlignLeft)  # type: ignore
            
            if "Current VIX" in text:
                self.current_vix_value_label = value_label
            if "Current SPX" in text:
                self.current_spx_value_label = value_label
            if "Yesterday VIX" in text:
                self.yesterday_vix_value_label = value_label
            

        data_layout.setColumnStretch(3, 1)

        # EMA Period Control
        # ema_frame = QFrame(self)
        # ema_layout = QHBoxLayout(ema_frame)
        # ema_layout.setContentsMargins(0, 5, 0, 0)
        # ema_layout.setSpacing(5)
        # period_label = QLabel("period :", self)
        # period_label.setFont(QFont('Segoe UI', 14))
        # ema_layout.addWidget(period_label)
        
        # self.ema_period = QLineEdit("50", self)
        # self.ema_period.setFixedSize(50, 30)
        # self.ema_period.setAlignment(Qt.AlignCenter)  # type: ignore
        # self.ema_period.setFont(QFont('Segoe UI', 14))
        # ema_layout.addWidget(self.ema_period)
        
        # min_label = QLabel("min", self)
        # min_label.setFont(QFont('Segoe UI', 14))
        # ema_layout.addWidget(min_label)
        
        # change_btn_ema = QPushButton("change", self)
        # change_btn_ema.setObjectName("change_button")
        # change_btn_ema.clicked.connect(self.update_ema_prices)
        # ema_layout.addWidget(change_btn_ema)
        # ema_layout.addStretch()
        
        # data_layout.addWidget(ema_frame, 4, 0, 1, 4)
        content_layout.addWidget(data_frame)

        # --- Trading Flag Frame ---
        trading_frame = QFrame(self)
        trading_frame.setObjectName("bordered_frame")
        trading_layout = QVBoxLayout(trading_frame)
        trading_layout.setSpacing(10)
        
        self.trading_flag_label = QLabel("", self)
        self.trading_flag_label.setFont(QFont('Segoe UI', 14))
        trading_layout.addWidget(self.trading_flag_label)

        # --- Trading Table ---
        table_widget = self.create_trading_table()
        trading_layout.addWidget(table_widget)

        # --- Controls Frame ---
        controls_frame = QFrame(self)
        controls_layout = QGridLayout(controls_frame)
        controls_layout.setContentsMargins(0, 10, 0, 0)
        controls_layout.setHorizontalSpacing(10)
        
        control_font = QFont('Segoe UI', 14)

        # Add Midpoint price label above Enter time
        self.current_net_price = "N/A"
        self.current_net_price_label = QLabel(f"Midpoint price : {self.current_net_price}", self)
        self.current_net_price_label.setFont(control_font)
        controls_layout.addWidget(self.current_net_price_label, 0, 0, 1, 3)

        # self.usd_portfolio_label = QLabel("USD Portfolio: N/A", self)
        # self.usd_portfolio_label.setFont(control_font)
        # controls_layout.addWidget(self.usd_portfolio_label, 0, 3, 1, 5)
        # Row 0: Enter time
        enter_time_label = QLabel("Enter time : ", self)
        enter_time_label.setFont(control_font)
        controls_layout.addWidget(enter_time_label, 1, 0)
        
        self.h_entry = QLineEdit("9", self)
        self.h_entry.setFixedSize(40, 32)
        self.h_entry.setAlignment(Qt.AlignCenter)  # type: ignore
        self.h_entry.setFont(control_font)
        controls_layout.addWidget(self.h_entry, 1, 1)

        h_label = QLabel(":", self)
        h_label.setFont(control_font)
        controls_layout.addWidget(h_label, 1, 2)
        
        self.m_entry = QLineEdit("55", self)
        self.m_entry.setFixedSize(40, 32)
        self.m_entry.setAlignment(Qt.AlignCenter)  # type: ignore
        self.m_entry.setFont(control_font)
        controls_layout.addWidget(self.m_entry, 1, 3)

        min_am_label = QLabel("AM", self)
        min_am_label.setFont(control_font)
        controls_layout.addWidget(min_am_label, 1, 4)
        
        # Row 1: Waiting limit
        waiting_limit_label = QLabel("Waiting limit : ", self)
        waiting_limit_label.setFont(control_font)
        controls_layout.addWidget(waiting_limit_label, 2, 0)

        self.w_entry = QLineEdit("20", self)
        self.w_entry.setFixedSize(40, 32)
        self.w_entry.setAlignment(Qt.AlignCenter)  # type: ignore
        self.w_entry.setFont(control_font)
        controls_layout.addWidget(self.w_entry, 2, 1)
        
        s_label = QLabel("s", self)
        s_label.setFont(control_font)
        controls_layout.addWidget(s_label, 2, 2)
        
        # Row 2: Max attempt & Offset
        max_attempt_label = QLabel("Max attempt : ", self)
        max_attempt_label.setFont(control_font)
        controls_layout.addWidget(max_attempt_label, 3, 0)
        
        self.a_entry = QLineEdit("5", self)
        self.a_entry.setFixedSize(40, 32)
        self.a_entry.setAlignment(Qt.AlignCenter)  # type: ignore
        self.a_entry.setFont(control_font)
        controls_layout.addWidget(self.a_entry, 3, 1)
        
        # offset_label = QLabel("Offset :", self)
        # offset_label.setFont(control_font)
        # controls_layout.addWidget(offset_label, 3, 3, Qt.AlignRight)  # type: ignore
        
        # self.o_entry = QLineEdit("0.004", self)
        # self.o_entry.setFixedWidth(80)
        # self.o_entry.setFixedHeight(32)
        # self.o_entry.setAlignment(Qt.AlignCenter)  # type: ignore
        # self.o_entry.setFont(control_font)
        # controls_layout.addWidget(self.o_entry, 3, 4)
        
        # Add QTY label and entry to the right of offset
        qty_label = QLabel("QTY :", self)
        qty_label.setFont(control_font)
        controls_layout.addWidget(qty_label, 3, 5)

        self.qty_entry = QLineEdit("2", self)
        self.qty_entry.setFixedWidth(60)
        self.qty_entry.setFixedHeight(32)
        self.qty_entry.setAlignment(Qt.AlignCenter)  # type: ignore
        self.qty_entry.setFont(control_font)
        controls_layout.addWidget(self.qty_entry, 3, 6)
        
        controls_layout.setColumnStretch(7, 1)
        
        trading_layout.addWidget(controls_frame)
        
        # --- Action Buttons ---
        action_frame = QFrame(self)
        action_layout = QHBoxLayout(action_frame)
        action_layout.setContentsMargins(0, 20, 0, 0)
        
        self.start_btn = QPushButton("Start", self)
        self.start_btn.setObjectName("start_button")
        self.start_btn.setFixedSize(100, 40)
        self.start_btn.clicked.connect(self.start)
        action_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop", self)
        self.stop_btn.setObjectName("stop_button")
        self.stop_btn.setFixedSize(100, 40)
        self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.setEnabled(False)
        action_layout.addWidget(self.stop_btn)
        action_layout.addStretch()
        trading_layout.addWidget(action_frame)

        content_layout.addWidget(trading_frame)
        
        # --- Log Frame ---
        log_frame = QFrame(self)
        log_frame.setObjectName("bordered_frame")
        log_layout = QVBoxLayout(log_frame)
        if connected:
            self.log_text = QTextEdit("API Status :connected", self)
        else:
            self.log_text = QTextEdit("API Status :disconnected", self) 
        self.log_text.setFont(QFont('Segoe UI', 8))
        self.log_text.setStyleSheet("border: none; background-color: #2C2F33; color: #99AAB5;")
        log_layout.addWidget(self.log_text)
        content_layout.addWidget(log_frame)

        # Timer for live clock
        timer = QTimer(self)
        timer.timeout.connect(self.update_time)
        timer.start(1000)
        

        # Timer for market price updates (every 2 seconds)
        # self.market_timer = QTimer(self)
        # self.market_timer.timeout.connect(self.update_market_prices)
        # self.market_timer.start(1000)

        # self.ema_timer = QTimer(self)
        # # self.ema_timer.timeout.connect(self.update_ema_prices)
        # # self.update_ema_prices()
        # self.ema_timer.start(60000)
        # self.update_usd_portfolio()


        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.check_order_status)
        self.monitor_timer.start(1000)


        self.setLayout(main_layout)
        self.show()
        # self.waiting_dialog.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:  # type: ignore
            if self.title_bar.geometry().contains(event.pos()):
                self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = QPoint(event.globalPos() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def update_time(self):
        """Updates the time label with the current date and time."""
        current_time_str = "current time : " + QDateTime.currentDateTime().toString('hh:mm:ss AP MMMM dd, yyyy')
        self.current_time.setText(current_time_str)

    # def update_usd_portfolio(self):
    #     # Get USD portfolio value from IB account values
    #     if hasattr(self, 'ib') and self.ib.isConnected():
    #         account_values = self.ib.accountValues()
    #         for v in account_values:
    #             if v.tag == 'TotalCashValue' and v.currency == 'USD':
    #                 self.usd_portfolio_label.setText(f"USD Portfolio: {v.value}")
    #                 return
    #     self.usd_portfolio_label.setText("USD Portfolio: N/A")

    def create_trading_table(self):
        table_frame = QFrame(self)
        self.table_layout = QVBoxLayout(table_frame)
        self.table_layout.setContentsMargins(0,0,0,0)
        self.table_layout.setSpacing(0)

        header_style = "background-color: #5865F2; color: white; padding: 8px; border: none; font-weight: bold;"
        columns = ["Type", "Strike", "Bid", "Ask"]
        column_stretches = [1, 1, 1, 1]
        
        header_widget = QFrame()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0,0,0,0)
        header_layout.setSpacing(1)

        for i, col in enumerate(columns):
            label = QLabel(col)
            label.setAlignment(Qt.AlignCenter)  # type: ignore
            label.setStyleSheet(header_style)
            if i == 0: label.setStyleSheet(header_style + "border-top-left-radius: 5px;")
            if i == len(columns) - 1: label.setStyleSheet(header_style + "border-top-right-radius: 5px;")
            header_layout.addWidget(label, column_stretches[i], Qt.AlignVCenter)  # type: ignore

        self.table_layout.addWidget(header_widget)
        
        # Table Rows
        buy_data = ("Call Buy", "", "", "")
        sell_data = ("Call Sell(30 ↑)", "", "", "")
        put_buy_data = ("Put Buy(closest to -0.3)", "", "", "")
        call_spread = ("Final Spread", "", "", "")

        buy_layout, buy_labels = self.create_trade_row(buy_data, is_odd=False)
        sell_layout, sell_labels = self.create_trade_row(sell_data, is_odd=False)
        put_buy_layout, put_buy_labels = self.create_trade_row(put_buy_data, is_odd=False)
        call_spread_layout, call_spread_labels = self.create_trade_row(call_spread, is_odd=False)
        self.buy_labels = buy_labels
        self.sell_labels = sell_labels
        self.put_buy_labels = put_buy_labels
        self.call_spread_labels = call_spread_labels
        self.table_layout.addWidget(buy_layout)
        self.table_layout.addWidget(sell_layout)
        self.table_layout.addWidget(put_buy_layout)
        self.table_layout.addWidget(call_spread_layout)

        return table_frame

    def create_trade_row(self, data, is_odd):
        row_widget = QFrame()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0,0,0,0)
        row_layout.setSpacing(1)

        bg_color = "#2C2F33" if is_odd else "#36393F"
        cell_style = f"background-color: {bg_color}; padding: 6px; border: none;"
        frame_cell_style = f"QFrame {{ background-color: {bg_color}; padding: 6px; border: none; }}"

        column_stretches = [1, 1, 1, 1]
        
        labels = []
        for i, item in enumerate(data):
            label = QLabel(str(item))
            label.setAlignment(Qt.AlignCenter)  # type: ignore
            label.setStyleSheet(cell_style)
            row_layout.addWidget(label, column_stretches[i], Qt.AlignVCenter)  # type: ignore
            labels.append(label)

        
        return row_widget, labels

    def update_lmt_value(self, lmt_label, entry):
        """Updates the LMT label with the value from the entry field."""
        lmt_label.setText(entry.text())

    def update_ema_label(self):
        """Updates the SPX EMA label based on the period input."""
        period = self.ema_period.text()
        self.spx_ema_label.setText(f"SPX EMA in {period} min")

    def close_application(self):
        """Disconnect from IB API and close the application"""
        try:
            if ib.isConnected():
                ib.disconnect()
                print("Disconnected from IB API")
        except Exception as e:
            print(f"Error disconnecting from IB API {e}")
        finally:
            self.close()
  

    def update_ema_prices(self):
        ema_period = int(self.ema_period.text())
        ema_price = self.get_spx_ema(ema_period)
        self.spx_ema_label.setText(f"SPX EMA in {ema_period} min")
        self.spx_ema_value_label.setText(f": {ema_price:.2f}")

        

    def start(self):
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.log_text.append(f"Trading bot started... : {self.current_time.text()}")
        now = datetime.now()
        hour = int(self.h_entry.text())
        minute = int(self.m_entry.text())
        self.target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if self.target_time < now:
            self.target_time += timedelta(days=1)
        
        self.waiting_timer = QTimer(self)
        self.waiting_timer.timeout.connect(self.wait_loop)
        self.waiting_timer.start(1000)
        self.waiting_message_shown = False

    def wait_loop(self):
        if datetime.now() > self.target_time:
            self.execute_order()
            self.waiting_timer.stop()
        else:
            remaining = (self.target_time - datetime.now())
            print(f"Waiting for {remaining} seconds until entry time...")
            if not self.waiting_message_shown:
                self.log_text.append("waiting...")
                self.waiting_message_shown = True



        # self.execute_order()


    def execute_order(self,first=True):
        if first:
            self.log_text.append(f"execute order...{self.midpoint}")
        else:
            self.log_text.append(f"execute order again...{self.midpoint}")
        try:
            print("tt")
            buy_leg = 0
            sell_leg = 0
            if buy_option_detail is not None:
                if buy_option_detail and buy_option_detail[0].contract is not None:
                    buy_leg = buy_option_detail[0].contract.conId
                    print(buy_leg)
                else:
                    print("Buy contract details not found!")
                    return

            if sell_option_detail is not None:
                if sell_option_detail and sell_option_detail[0].contract is not None:
                    sell_leg = sell_option_detail[0].contract.conId
                else:
                    print("Sell contract details not found!")
                    return
            legs = [
                ComboLeg(conId=buy_leg, ratio=1, action='BUY', exchange='CBOE'),
                ComboLeg(conId=sell_leg, ratio=1, action='SELL', exchange='CBOE')
            ]
            combo = Contract()
            combo.symbol = 'SPX'
            combo.secType = 'BAG'
            combo.currency = 'USD'
            combo.exchange = 'CBOE'
            combo.comboLegs = legs

            
            
            # offset = float(self.o_entry.text())
            qty = int(self.qty_entry.text())
            self.waiting_time = int(self.w_entry.text())
            max_attempt = int(self.a_entry.text())
            
            if first:
                order = LimitOrder('BUY',qty , self.midpoint)
                # order = MarketOrder('BUY',qty)

                self.remain_attempt = max_attempt;
                self.remain_waiting_time = self.waiting_time;
            else:
                order = LimitOrder('BUY',qty , self.midpoint)
                # order = MarketOrder('BUY',qty)
                # time.sleep(3)

            self.ordered_trade = ib.placeOrder(combo, order)
        except Exception as e:
            self.log_text.append(f"Error executing order: {e}")
            


    def check_order_status(self):
        if self.ordered_trade is None:
            return

        
        status = self.ordered_trade.orderStatus.status
        self.remain_waiting_time -= 1
        print(status,self.remain_waiting_time)
        if status == 'Filled' or status == 'Inactive':
            self.ordered_trade = None
            self.monitor_timer.stop()
            self.log_text.append(f"Order {status}... : {self.current_time.text()}")
            return

        if self.remain_waiting_time == 0:
            if hasattr(self, 'ordered_trade') and self.ordered_trade is not None:
                ib.cancelOrder(self.ordered_trade.order)
            if self.remain_attempt == 0:
                self.ordered_trade = None
                self.stop()
                return
            else :
                self.execute_order(False)
            self.remain_attempt -= 1
            self.remain_waiting_time = self.waiting_time


            
                
                




    def stop(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        print("stop")
        if self.waiting_timer.isActive():
            self.waiting_timer.stop()
            self.log_text.append(f"Trading bot stopped... : {self.current_time.text()}")
            return

        if hasattr(self, 'ordered_trade') and self.ordered_trade is not None:
            self.log_text.append(f"Order canceled... : {self.current_time.text()}")
            ib.cancelOrder(self.ordered_trade.order)
            self.ordered_trade = None
                

    
    # def update_market_prices(self):
    #     self.ib.sleep(0.3)
    #     try:
    #         if hasattr(self, 'current_vix_value_label'):
    #             self.current_vix_value_label.setText(f": {self.get_current_vix()}")
    #             if self.yesterday_vix > self.current_vix:
    #                 self.current_vix_value_label.setStyleSheet("color: #43B581; font-weight: bold;")
    #                 self.trade_flag = True
    #             else:
    #                 self.current_vix_value_label.setStyleSheet("color: #ED4245; font-weight: bold;")
    #                 self.trade_flag = False
    #         if hasattr(self, 'current_spx_value_label'):
    #             self.current_spx_value_label.setText(f": {self.get_current_spx()}")
    #             if self.current_spx > self.spx_ema:
    #                 self.current_spx_value_label.setStyleSheet("color: #43B581; font-weight: bold;")
    #                 self.trade_flag = True
    #             else:
    #                 self.current_spx_value_label.setStyleSheet("color: #ED4245; font-weight: bold;")
    #                 self.trade_flag = False
            
    #         self.get_buy_sell_strike()
            
    #         # Update trading flag label
    #         if hasattr(self, 'trading_flag_label'):
    #             if self.trade_flag:
    #                 self.trading_flag_label.setText("Trading flag : <b style='color:#43B581;'>Please trade</b>")
    #             else:
    #                 self.trading_flag_label.setText("Trading flag : <b style='color:#ED4245;'>Don't trade</b>")
    #     except Exception as e:
    #         print(f"Error updating market prices: {e}")



async def get_yesterday_close(ib, contract):
    # Fetch 5 or more days to be safe for weekends/holidays
    bars = await ib.reqHistoricalDataAsync(
        contract, 
        endDateTime= '',
        barSizeSetting='1 day',
        durationStr='2 D',
        whatToShow='TRADES',
        useRTH=True
    )
    if bars:
        yesterday_vix = float(bars[0].close)
        return yesterday_vix
    return None


async def get_spx_ema(ib,contract):
            spx_historical =await ib.reqHistoricalDataAsync(
                contract,
                endDateTime= datetime.now(),
                barSizeSetting='1 min',
                durationStr='3000 S',
                whatToShow='TRADES',
                useRTH=True
            )
            if spx_historical:
                spx_df = pd.DataFrame({'price':[
                    bar.close for bar in spx_historical
                ]})
                spx_df['ema'] = spx_df['price'].ewm(span=50, adjust=False).mean()
                last_ema = spx_df['ema'].iloc[-1]
                return last_ema
            return None

def select_closest_around(lst, threshold, n):
    # Find all elements smaller than threshold
    smaller = [x for x in lst if x < threshold]
    # Return the last n elements
    return smaller[-n:]

async def fetch_data(ui,mode, loop):
    global connected,ib
    
    try : 
        if mode == 1 : 
            await ib.connectAsync('127.0.0.1', 7496, clientId=1)
        if mode == 2 : 
            await ib.connectAsync('127.0.0.1', 7497, clientId=1)
            print("start")
        if ib.isConnected : 
            connected = True

            
        spx_contract = Index(symbol='SPX', exchange='CBOE')
        vix_contract = Index(symbol='VIX', exchange='CBOE')

        ######################
        print("Requesting option chain data for SPX...")
        detail = await ib.reqContractDetailsAsync(spx_contract)
        contract_info = detail[0].contract
        # print(contract_info)
        chains = await ib.reqSecDefOptParamsAsync(contract_info.symbol, '', contract_info.secType, contract_info.conId)
        today_str = datetime.now().strftime('%Y%m%d')
        strikes = []
        for chain in chains:
            if chain.exchange == "CBOE" and chain.tradingClass == 'SPXW':
                strikes = chain.strikes
        
        



        # # Extract all option contracts
        # option_contracts = [detail.contract for detail in details]
        # print(option_contracts)
        # # List all available expiration dates and strikes
        # expirations = sorted(set([opt.lastTradeDateOrContractMonth for opt in option_contracts]))
        # strikes = sorted(set([opt.strike for opt in option_contracts]))

        # print(f"\nAvailable expiration dates: {expirations}")
        # print(f"\nAvailable strikes: {strikes}")

        # # Filter options expiring today
        # today_str = datetime.now().strftime('%Y%m%d')
        # today_options = [
        #     opt for opt in option_contracts
        #     if opt.lastTradeDateOrContractMonth.startswith(today_str)
        # ]

        # print(f"\nNumber of options expiring today ({today_str}): {len(today_options)}")

        # # Sample output: print details of first 10 options expiring today
        # print("\nSample options expiring today:")
        # for opt in today_options[:10]:
        #     print(f"Symbol: {opt.symbol}, Expiry: {opt.lastTradeDateOrContractMonth}, Strike: {opt.strike}, Right: {opt.right}")

        # option_chain = await ib.reqSecDefOptParamsAsync(spx_contract.symbol, '', spx_contract.secType, spx_contract.conId)
        # expirations = [opt.expirations for opt in option_chain][0]
    
        # # For today’s expiration date, we’ll use the first expiration that matches today's date
        # todays_expiration = next((exp for exp in expirations if exp.startswith(today)), None)
        
        # if todays_expiration is None:
        #     print(f"No options found for today's expiration: {today}")
        #     return
        
        # # Fetch strikes for the chosen expiration date
        # strikes = [opt.strikes for opt in option_chain if opt.expirations == [todays_expiration]][0]
        
        # # Create Option contracts for Calls and Puts
        # options = []
        # for strike in strikes:
        #     call = Option('SPX', todays_expiration, strike, 'C', 'SMART')
        #     put = Option('SPX', todays_expiration, strike, 'P', 'SMART')
        #     options.append(call)
        #     options.append(put)
        
        # # Qualify contracts (to get more details)
        # ib.qualifyContracts(*options)
        
        # # Subscribe to real-time market data for these options
        # market_data = []
        # for option in options:
        #     mkt_data = ib.reqMktData(option, '', False, False)  # Request live market data (not snapshot)
        #     market_data.append(mkt_data)
            
        #     # Attach event listener for real-time updates (delta changes)
        #     mkt_data.updateEvent += on_market_data_update
        
        # def on_market_data_update(msg):
        #     if msg.field == 21:  # Field 21 corresponds to 'delta' in IBKR
        #         print(f"Real-Time Delta for {msg.contract.symbol} {msg.contract.lastTradeDateOrContractMonth} {msg.contract.strike} {msg.contract.right}: {msg.value}")

    
        ######################

        
        buy_strike_price = 0


        await ib.qualifyContractsAsync(spx_contract)
        await ib.qualifyContractsAsync(vix_contract)
        ticker_spx = ib.reqMktData(spx_contract)
        ticker_vix = ib.reqMktData(vix_contract)
        

        yesterday_close = await get_yesterday_close(ib, vix_contract)

        # print("yesterday closing price : ", yesterday_close)
        if yesterday_close != None : 
            ui.signals.yesterday_close.emit(yesterday_close)


        

        
                # print("ema spx price : ", last_ema)
                # ui.signals.ema_spx.emit(last_ema)
        async def ema_timer():
            last_ema = await get_spx_ema(ib, spx_contract)
            if last_ema != None:
                ui.signal.ema_spx.emit(last_ema)


        
        # thread = QThread()

        # def thread_function():
            
        #     timer = QTimer()
        #     timer.timeout.connect(ema_timer)
        #     timer.start(1000)  # 1 second timer
        #     thread.exec_()

        
        # thread.run = thread_function
        # thread.start()
        async def ema_spx_task():
            spx_historical = await ib.reqHistoricalDataAsync(
                spx_contract,
                endDateTime='',
                barSizeSetting='1 min',
                durationStr='3000 S',
                whatToShow='TRADES',
                useRTH=True
            )

            if spx_historical:
                spx_df = pd.DataFrame({
                    'price': [bar.close for bar in spx_historical]
                })
                spx_df['ema'] = spx_df['price'].ewm(span=50, adjust=False).mean()
                last_ema = spx_df['ema'].iloc[-1]
                # print("ema_spx:", last_ema)
                ui.signals.ema_spx.emit(last_ema)

        
        def ema_spx_historical():
            asyncio.create_task(ema_spx_task())
        ticker_buy = None
        ticker_sell = None
        async def strike_options_task(spx_price):
            
            global buy_option_contract,sell_option_contract,buy_option_detail,sell_option_detail
            nonlocal buy_strike_price,ticker_buy,ticker_sell,strikes
            # print(spx_price)
            today = datetime.now().strftime('%Y%m%d')
            if buy_strike_price != (round(spx_price / 5) * 5) :
                print("__________ttt")
                buy_strike_price = round(spx_price / 5) * 5
                sell_strike_price = buy_strike_price  + 30
                
                buy_option_contract = Option(
                    symbol='SPX',
                    lastTradeDateOrContractMonth=today,
                    strike=buy_strike_price,
                    right='C',
                    exchange='CBOE'
                )
                sell_option_contract = Option(
                    symbol='SPX',
                    lastTradeDateOrContractMonth=today,
                    strike=sell_strike_price,
                    right='C',
                    exchange='CBOE'
                )
                buy_option_detail = await ib.reqContractDetailsAsync(buy_option_contract)
                sell_option_detail = await ib.reqContractDetailsAsync(sell_option_contract)
                await ib.qualifyContractsAsync(buy_option_contract)
                await ib.qualifyContractsAsync(sell_option_contract)
                if ticker_buy is not None and ticker_sell is not None:
                    ticker_buy.updateEvent.clear()
                    ticker_sell.updateEvent.clear()
                ticker_buy = ib.reqMktData(buy_option_contract)
                ticker_sell = ib.reqMktData(sell_option_contract)
                ticker_buy.updateEvent += on_buy_update
                ticker_sell.updateEvent += on_sell_update

                ui.signals.buy_strike_price.emit(buy_strike_price)
                ui.signals.sell_strike_price.emit(sell_strike_price)

        last_delta = dict()
        ticker_put = dict()
        async def efficient_option_task(efficient_strikes):
            nonlocal last_delta,ticker_put
            print(efficient_strikes)
            for strike in efficient_strikes:
                last_delta[strike] = 0
                today = datetime.now().strftime('%Y%m%d')
                put_option_contract = Option(
                                symbol='SPX',
                                lastTradeDateOrContractMonth=today,
                                strike=strike,
                                right='P',
                                exchange='CBOE'
                            )
                await ib.qualifyContractsAsync(put_option_contract)
                if hasattr(ticker_put,str(strike)):
                    ticker_put[strike].updateEvent.clear()
                ticker_put[strike] = ib.reqMktData(put_option_contract)
                    # print(ticker_put)  

                ticker_put[strike].updateEvent += on_put_delta
        current_detal = dict()
        def on_put_delta(ticker):
            nonlocal current_detal
            if ticker.bidGreeks != None and ticker.bidGreeks.delta !=None:
                if last_delta[ticker.contract.strike] !=  ticker.bidGreeks.delta:
                    print(last_delta)
                    closest_key = min(last_delta, key=lambda k: abs(last_delta[k] - (-0.3)))
                    closest_value = last_delta[closest_key]
                    # print(closest_key,closest_value)
                    last_delta[ticker.contract.strike] = ticker.bidGreeks.delta
            
           
                  
                


        def get_buy_sell_strike(spx_price):
            asyncio.create_task(strike_options_task(spx_price))
        
        def efficient_option(efficient_strikes):
            asyncio.create_task(efficient_option_task(efficient_strikes))
        old_efficient_strikes = []
        def on_spx_update(ticker):
            nonlocal old_efficient_strikes
            ema_spx_historical()
            if ticker.last : 
                # print(ticker.last)
                ui.signals.spx_price_updated.emit(ticker.last)
                get_buy_sell_strike(ticker.last)
                
                efficient_strikes = select_closest_around(strikes,ticker.last,5)
                if old_efficient_strikes != efficient_strikes:
                    efficient_option(efficient_strikes)
                    old_efficient_strikes = efficient_strikes
                
            
                

        
        def on_vix_update(ticker):
            # emit signal to update UI
            if ticker.last: 
                ui.signals.vix_price_updated.emit(ticker.last)
        def on_buy_update(ticker):
            ui.signals.buy_option_updated.emit((ticker.bid,ticker.ask))
        def on_sell_update(ticker):
            ui.signals.sell_option_updated.emit((ticker.bid,ticker.ask))
        ticker_spx.updateEvent += on_spx_update
        ticker_vix.updateEvent += on_vix_update

        

        buy_ticker = ib.reqMktData(buy_option_contract, '', False, False)
        sell_ticker = ib.reqMktData(sell_option_contract, '', False, False)

        

    except Exception as e:
        print("e:",e)


    # Keep running to receive updates
    while True:
        await asyncio.sleep(1)

def start_asyncio_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


def main():
    app = QApplication(sys.argv)
    mode_dialog = TwoRadioDialog()
    if mode_dialog.exec_() == QDialog.Accepted:
        mode = mode_dialog.selected_option()
        # print("execution mode:", mode)
        window = TradingAppQt()
        new_loop = asyncio.new_event_loop()
        
        timer = QTimer()
        timer.timeout.connect(lambda: None) 
        timer.start(100)  # run every 100 ms

        asyncio.ensure_future(fetch_data(window, mode, new_loop), loop=new_loop)

        
        threading.Thread(target=start_asyncio_loop, args=(new_loop,), daemon=True).start()
        
        sys.exit(app.exec_())



if __name__ == '__main__':
    main() 