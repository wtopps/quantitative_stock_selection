#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股次日冲高标的筛选脚本 v6.0
基于量化条件 + 月份主题 + 形态分析 + 主力资金流向 + 三维度综合评估

核心升级（v6.0）：
1. 资金流向深度分析：评估主力与整体资金一致性、流量占比
2. 市场相对强度判断：与沪深300/上证指数对比，识别真正强势股
3. 关键价格位置确认：突破有效性分析、支撑稳固性评估
4. 三维度综合评分：资金共振 + 相对强势 + 价格位置 = 最终决策

原有功能：
- 超大单和大单资金流向监控
- 指定板块/概念筛选功能
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')


# ============================================================
# 月份主题配置
# ============================================================
MONTHLY_THEMES = {
    1: {
        "name": "消费预期",
        "logic": "春节效应，资金围绕吃喝玩乐、衣食住行反复炒作",
        "keywords": [
            "白酒", "啤酒", "食品", "饮料", "零食", "乳业", "调味品",
            "旅游", "酒店", "餐饮", "免税", "影视", "院线", "传媒",
            "服装", "纺织", "家电", "零售", "商业", "百货", "超市",
            "黄金珠宝", "化妆品", "医美", "预制菜"
        ],
        "concepts": ["大消费", "春节概念", "免税概念", "预制菜"]
    },
    2: {
        "name": "农业预期",
        "logic": "中央一号文件落地，春耕种子、农机、化肥等板块易拉升",
        "keywords": [
            "种业", "种子", "农业", "化肥", "农药", "饲料", "养殖",
            "猪肉", "鸡肉", "农机", "灌溉", "转基因", "粮食",
            "大豆", "玉米", "小麦", "水产", "乡村振兴"
        ],
        "concepts": ["乡村振兴", "转基因", "猪肉概念", "鸡肉概念"]
    },
    3: {
        "name": "两会预期",
        "logic": "大会定调全年方向，政策预期板块易被爆炒",
        "keywords": [
            "新能源", "光伏", "风电", "储能", "氢能", "锂电",
            "半导体", "芯片", "人工智能", "数字经济", "信创",
            "军工", "国防", "航天", "环保", "碳中和", "新基建",
            "医疗", "医药", "养老", "教育"
        ],
        "concepts": ["国产替代", "数字经济", "新能源", "碳中和"]
    },
    4: {
        "name": "年报行情",
        "logic": "年报和季报集中披露期，个股易爆雷或被ST，建议多看少动",
        "keywords": [
            "业绩预增", "高送转", "分红"
        ],
        "concepts": ["业绩预增", "高送转"],
        "warning": "⚠️ 4月年报季，个股易爆雷，建议谨慎操作，多看少动！"
    },
    5: {
        "name": "电力预期",
        "logic": "沿海地区天气升温，用电负荷飙升，电力板块易有动作",
        "keywords": [
            "电力", "火电", "水电", "核电", "绿电", "电网",
            "特高压", "输配电", "智能电网", "充电桩", "虚拟电厂",
            "空调", "制冷", "家电"
        ],
        "concepts": ["电力", "特高压", "虚拟电厂", "充电桩"]
    },
    6: {
        "name": "中报预期",
        "logic": "五穷六绝七翻身，业绩预增方向提前炒作",
        "keywords": [
            "业绩预增", "中报预增", "高成长",
            "新能源车", "锂电池", "光伏", "储能",
            "半导体", "消费电子"
        ],
        "concepts": ["业绩预增", "高成长", "次新股"]
    },
    7: {
        "name": "电力与水利",
        "logic": "高温天气限电政策，叠加干旱、洪涝等天气，水利地下管网板块迎炒作",
        "keywords": [
            "电力", "火电", "水电", "水利", "水务", "污水处理",
            "地下管网", "管道", "防汛", "抗旱", "节水灌溉",
            "空调", "制冷", "冰箱"
        ],
        "concepts": ["电力", "水利", "地下管网", "抗旱概念"]
    },
    8: {
        "name": "科技",
        "logic": "华为、三星、苹果等大厂新品发布集中，科技股易起飞",
        "keywords": [
            "消费电子", "手机", "苹果", "华为", "小米",
            "半导体", "芯片", "存储", "面板", "显示",
            "光学", "摄像头", "声学", "电池", "快充",
            "VR", "AR", "MR", "折叠屏", "卫星通信"
        ],
        "concepts": ["华为概念", "苹果概念", "消费电子", "折叠屏"]
    },
    9: {
        "name": "消费旅游与酒店",
        "logic": "国庆黄金周提前一个月布局，资金炒作旅游、酒店板块",
        "keywords": [
            "旅游", "酒店", "景区", "航空", "机场", "免税",
            "餐饮", "白酒", "啤酒", "食品", "休闲食品",
            "出行", "租车", "在线旅游"
        ],
        "concepts": ["旅游", "免税概念", "酒店餐饮", "航空"]
    },
    10: {
        "name": "电商与物流",
        "logic": "双11促销预热，物流快递、线上零售板块曝光火爆",
        "keywords": [
            "快递", "物流", "仓储", "冷链", "电商",
            "跨境电商", "直播电商", "网红经济",
            "零售", "百货", "超市", "支付"
        ],
        "concepts": ["快递物流", "跨境电商", "网红经济", "直播电商"]
    },
    11: {
        "name": "供热",
        "logic": "入冬后供暖需求暴增，煤炭、燃气板块易拉升",
        "keywords": [
            "煤炭", "焦煤", "焦炭", "天然气", "燃气", "供热",
            "热力", "集中供暖", "清洁能源", "油气", "石油",
            "电力", "火电"
        ],
        "concepts": ["煤炭", "天然气", "供热", "油气"]
    },
    12: {
        "name": "妖股与跨年行情",
        "logic": "跨年妖股和低价股迎资金扎堆炒作，机构排名、玄学生肖等因素推动",
        "keywords": [
            "次新股", "小盘股", "超跌", "低价股",
            "元宇宙", "数字货币", "区块链", "游戏",
            "传媒", "影视", "文化"
        ],
        "concepts": ["次新股", "超跌反弹", "跨年行情"],
        "special": "关注生肖概念股（蛇年概念等）"
    }
}


class StockScreener:
    def __init__(self, target_sector=None):
        self.today = datetime.now().strftime('%Y%m%d')
        self.current_month = datetime.now().month
        self.theme = MONTHLY_THEMES.get(self.current_month, {})
        self.results = []
        self.concept_stocks = {}  # 缓存概念板块数据
        self.fund_flow_data = None  # 缓存资金流向数据
        self.target_sector = target_sector  # 目标板块/概念
        self.market_index_data = None  # 缓存大盘指数数据
        self.index_history = {}  # 缓存指数历史数据
        
    def print_header(self):
        """打印头部信息"""
        print("=" * 70)
        print("【A股次日冲高标的筛选系统 v6.0】")
        print(f"筛选日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("🆕 v6.0升级: 资金共振分析 + 市场相对强度 + 关键价格位置")
        print("=" * 70)
        
        # 如果指定了目标板块
        if self.target_sector:
            print(f"\n🎯 指定板块筛选: 【{self.target_sector}】")
        else:
            # 显示当月主题
            print(f"\n📅 当前月份: {self.current_month}月")
            print(f"🎯 本月主题: 【{self.theme.get('name', '未知')}】")
            print(f"💡 核心逻辑: {self.theme.get('logic', '')}")
            
            if self.theme.get('warning'):
                print(f"\n{self.theme['warning']}")
            if self.theme.get('special'):
                print(f"🌟 特别关注: {self.theme['special']}")
            
            print(f"\n🔍 重点关注板块: {', '.join(self.theme.get('keywords', [])[:10])}...")
        print("-" * 70)
    
    def list_all_concepts(self):
        """列出所有可用的概念板块"""
        try:
            print("\n📋 正在获取所有概念板块...")
            df = ak.stock_board_concept_name_em()
            if df is not None and not df.empty:
                print(f"\n✅ 共获取到 {len(df)} 个概念板块\n")
                print("=" * 70)
                print("概念板块列表:")
                print("=" * 70)
                
                # 按列显示
                for i in range(0, len(df), 3):
                    row_items = []
                    for j in range(3):
                        if i + j < len(df):
                            name = df.iloc[i + j]['板块名称']
                            row_items.append(f"{name:20s}")
                    print("  " + "".join(row_items))
                
                return df
        except Exception as e:
            print(f"❌ 获取概念板块失败: {e}")
        return None
    
    def list_all_industries(self):
        """列出所有可用的行业板块"""
        try:
            print("\n📋 正在获取所有行业板块...")
            df = ak.stock_board_industry_name_em()
            if df is not None and not df.empty:
                print(f"\n✅ 共获取到 {len(df)} 个行业板块\n")
                print("=" * 70)
                print("行业板块列表:")
                print("=" * 70)
                
                # 按列显示
                for i in range(0, len(df), 3):
                    row_items = []
                    for j in range(3):
                        if i + j < len(df):
                            name = df.iloc[i + j]['板块名称']
                            row_items.append(f"{name:20s}")
                    print("  " + "".join(row_items))
                
                return df
        except Exception as e:
            print(f"❌ 获取行业板块失败: {e}")
        return None
    
    def get_sector_stocks(self, sector_name):
        """
        获取指定板块/概念的股票代码列表
        先尝试概念板块，再尝试行业板块
        """
        print(f"\n🔍 正在查找板块【{sector_name}】的成分股...")
        
        # 1. 先尝试概念板块
        try:
            df = ak.stock_board_concept_cons_em(symbol=sector_name)
            if df is not None and not df.empty:
                codes = df['代码'].tolist()
                print(f"✅ 在概念板块中找到 {len(codes)} 只股票")
                return codes, 'concept'
        except:
            pass
        
        # 2. 再尝试行业板块
        try:
            df = ak.stock_board_industry_cons_em(symbol=sector_name)
            if df is not None and not df.empty:
                codes = df['代码'].tolist()
                print(f"✅ 在行业板块中找到 {len(codes)} 只股票")
                return codes, 'industry'
        except:
            pass
        
        print(f"❌ 未找到板块【{sector_name}】，请检查板块名称是否正确")
        return [], None
        
    def get_realtime_data(self, sector_codes=None):
        """
        获取A股实时行情数据
        如果指定了sector_codes，则只获取这些股票的数据
        """
        try:
            df = ak.stock_zh_a_spot_em()
            
            # 如果指定了板块股票代码，进行筛选
            if sector_codes:
                df = df[df['代码'].isin(sector_codes)]
                print(f"\n📊 获取到板块内 {len(df)} 只股票的实时数据")
            else:
                print(f"\n📊 获取到 {len(df)} 只股票的实时数据")
            
            return df
        except Exception as e:
            print(f"❌ 获取实时数据失败: {e}")
            return None
    
    def get_all_fund_flow_data(self):
        """
        获取所有股票的实时资金流向数据（仅调用一次，缓存结果）
        返回：包含所有股票资金流向的DataFrame
        """
        if self.fund_flow_data is not None:
            return self.fund_flow_data
        
        try:
            print("   📥 正在获取全市场资金流向数据...")
            df = ak.stock_individual_fund_flow_rank(indicator="今日")
            if df is not None and not df.empty:
                self.fund_flow_data = df
                print(f"   ✅ 成功获取 {len(df)} 只股票的资金流向数据")
                return df
        except Exception as e:
            print(f"   ⚠️ 获取资金流向数据失败: {e}")
            self.fund_flow_data = pd.DataFrame()  # 空DataFrame避免重复调用
        return pd.DataFrame()
    
    def get_stock_individual_fund_flow(self, stock_code):
        """
        从缓存中获取个股实时资金流向数据
        返回：超大单净流入、大单净流入、中单净流入、小单净流入等
        """
        fund_flow_df = self.get_all_fund_flow_data()
        
        if fund_flow_df.empty:
            return None
        
        try:
            stock_data = fund_flow_df[fund_flow_df['代码'] == stock_code]
            if not stock_data.empty:
                return stock_data.iloc[0]
        except Exception as e:
            pass
        return None
    
    def analyze_fund_flow_signal(self, stock_code, stock_name):
        """
        分析个股资金流向信号
        返回：(信号类型, 信号强度, 详细数据)
        
        信号类型：
        - 'STRONG_BUY': 超大单强力流入（看涨）
        - 'BUY': 主力资金流入（看涨）
        - 'SELL': 主力资金流出（看跌/风险）
        - 'STRONG_SELL': 超大单和大单流出（强烈看跌）
        - 'NEUTRAL': 中性信号
        """
        fund_data = self.get_stock_individual_fund_flow(stock_code)
        
        if fund_data is None:
            return 'UNKNOWN', 0, {}
        
        try:
            # 提取关键资金流向指标
            super_large_net = fund_data.get('超大单净流入-净额', 0)  # 超大单净流入净额
            large_net = fund_data.get('大单净流入-净额', 0)  # 大单净流入净额
            super_large_pct = fund_data.get('超大单净流入-净占比', 0)  # 超大单净流入占比
            large_pct = fund_data.get('大单净流入-净占比', 0)  # 大单净流入占比
            
            # 主力资金 = 超大单 + 大单
            main_force_net = super_large_net + large_net
            main_force_pct = super_large_pct + large_pct
            
            # 数据字典
            detail = {
                '超大单净流入': super_large_net,
                '大单净流入': large_net,
                '主力净流入': main_force_net,
                '超大单占比': super_large_pct,
                '大单占比': large_pct,
                '主力占比': main_force_pct
            }
            
            # 信号判定逻辑
            # 1. 强烈看涨信号：超大单往里冲
            if super_large_net > 0 and large_net > 0 and super_large_pct > 5:
                return 'STRONG_BUY', 10, detail
            
            # 2. 看涨信号：主力资金净流入
            if main_force_net > 0 and main_force_pct > 3:
                return 'BUY', 7, detail
            
            # 3. 强烈看跌信号：超大单和大单都在跑
            if super_large_net < 0 and large_net < 0 and main_force_pct < -5:
                return 'STRONG_SELL', -10, detail
            
            # 4. 看跌信号：主力资金净流出
            if main_force_net < 0 and main_force_pct < -3:
                return 'SELL', -7, detail
            
            # 5. 中性信号
            return 'NEUTRAL', 0, detail
            
        except Exception as e:
            return 'UNKNOWN', 0, {}

    def analyze_fund_flow_depth(self, stock_code, stock_name, turnover_amount):
        """
        资金流向深度分析（v6.0新增）
        评估维度：
        1. 资金一致性：主力资金与整体资金流向是否一致
        2. 流量占比：净流入/流出金额占成交额的比例

        返回：(一致性评分, 流量占比评分, 详细数据)
        """
        fund_data = self.get_stock_individual_fund_flow(stock_code)

        if fund_data is None:
            return 0, 0, {'一致性': '未知', '流量占比': 0}

        try:
            # 提取各类资金流向
            super_large_net = fund_data.get('超大单净流入-净额', 0)
            large_net = fund_data.get('大单净流入-净额', 0)
            medium_net = fund_data.get('中单净流入-净额', 0)
            small_net = fund_data.get('小单净流入-净额', 0)

            # 主力资金 = 超大单 + 大单
            main_force_net = super_large_net + large_net
            # 整体资金 = 所有资金净流入
            total_net = super_large_net + large_net + medium_net + small_net
            # 散户资金 = 中单 + 小单
            retail_net = medium_net + small_net

            # === 1. 资金一致性分析 ===
            consistency_score = 0
            consistency_status = ""

            # 主力和整体资金方向一致性
            if main_force_net > 0 and total_net > 0:
                # 主力流入 + 整体流入 = 强一致性（最佳）
                consistency_score = 10
                consistency_status = "强一致流入"
            elif main_force_net > 0 and total_net < 0 and abs(main_force_net) > abs(retail_net):
                # 主力流入但散户流出，主力力度更大 = 主力吸筹
                consistency_score = 7
                consistency_status = "主力吸筹"
            elif main_force_net > 0 and total_net < 0:
                # 主力流入但整体流出 = 背离，需警惕
                consistency_score = 3
                consistency_status = "资金背离"
            elif main_force_net < 0 and total_net < 0:
                # 主力流出 + 整体流出 = 强一致性流出（危险）
                consistency_score = -10
                consistency_status = "一致流出"
            elif main_force_net < 0 and total_net > 0:
                # 主力流出但整体流入 = 主力出货
                consistency_score = -5
                consistency_status = "主力出货"
            else:
                consistency_score = 0
                consistency_status = "资金平衡"

            # === 2. 流量占比分析 ===
            flow_ratio_score = 0
            flow_ratio = 0

            if turnover_amount and turnover_amount > 0:
                # 主力净流入占成交额比例
                flow_ratio = (main_force_net / turnover_amount) * 100

                if flow_ratio > 10:
                    flow_ratio_score = 10  # 超强流入
                elif flow_ratio > 5:
                    flow_ratio_score = 7   # 强流入
                elif flow_ratio > 2:
                    flow_ratio_score = 5   # 中等流入
                elif flow_ratio > 0:
                    flow_ratio_score = 3   # 弱流入
                elif flow_ratio > -2:
                    flow_ratio_score = 0   # 基本平衡
                elif flow_ratio > -5:
                    flow_ratio_score = -3  # 弱流出
                elif flow_ratio > -10:
                    flow_ratio_score = -7  # 强流出
                else:
                    flow_ratio_score = -10 # 超强流出

            detail = {
                '一致性': consistency_status,
                '一致性得分': consistency_score,
                '主力净流入': main_force_net,
                '整体净流入': total_net,
                '散户净流入': retail_net,
                '流量占比': flow_ratio,
                '流量占比得分': flow_ratio_score
            }

            return consistency_score, flow_ratio_score, detail

        except Exception as e:
            return 0, 0, {'一致性': '分析失败', '流量占比': 0}

    def get_market_index_history(self, index_code='000300', days=120):
        """
        获取大盘指数历史数据（用于相对强度对比）
        index_code: 000300=沪深300, 000001=上证指数
        """
        cache_key = f"{index_code}_{days}"
        if cache_key in self.index_history:
            return self.index_history[cache_key]

        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days+30)).strftime('%Y%m%d')

            df = ak.index_zh_a_hist(
                symbol=index_code,
                period="daily",
                start_date=start_date,
                end_date=end_date
            )

            if df is not None and not df.empty:
                self.index_history[cache_key] = df
                return df
        except Exception as e:
            pass
        return None

    def analyze_relative_strength(self, stock_code, stock_name, current_change):
        """
        市场相对强度判断（v6.0新增）
        将个股走势与大盘核心指数进行对比

        评估维度：
        1. 当日相对强度：今日涨跌幅 vs 大盘涨跌幅
        2. 近期相对强度：近5日/10日/20日累计涨跌 vs 大盘
        3. 强弱趋势：在大盘上涨时涨更多，下跌时跌更少

        返回：(相对强度评分, 详细数据)
        """
        try:
            # 获取大盘实时数据
            if self.market_index_data is None:
                self.market_index_data = ak.stock_zh_index_spot_em()

            # 获取沪深300和上证指数的涨跌幅
            hs300 = self.market_index_data[self.market_index_data['代码'] == '000300']
            sh_index = self.market_index_data[self.market_index_data['代码'] == '000001']

            hs300_change = hs300['涨跌幅'].values[0] if not hs300.empty else 0
            sh_change = sh_index['涨跌幅'].values[0] if not sh_index.empty else 0

            # 使用沪深300作为主要基准
            benchmark_change = hs300_change

            # === 1. 当日相对强度 ===
            daily_excess = current_change - benchmark_change

            # === 2. 近期相对强度（需要历史数据）===
            stock_hist = self.get_historical_data(stock_code, days=30)
            index_hist = self.get_market_index_history('000300', days=30)

            rs_5d = 0
            rs_10d = 0
            rs_20d = 0
            trend_score = 0

            if stock_hist is not None and index_hist is not None:
                if len(stock_hist) >= 20 and len(index_hist) >= 20:
                    # 计算累计涨跌幅
                    stock_5d = (stock_hist['收盘'].iloc[-1] / stock_hist['收盘'].iloc[-6] - 1) * 100 if len(stock_hist) >= 6 else 0
                    stock_10d = (stock_hist['收盘'].iloc[-1] / stock_hist['收盘'].iloc[-11] - 1) * 100 if len(stock_hist) >= 11 else 0
                    stock_20d = (stock_hist['收盘'].iloc[-1] / stock_hist['收盘'].iloc[-21] - 1) * 100 if len(stock_hist) >= 21 else 0

                    index_5d = (index_hist['收盘'].iloc[-1] / index_hist['收盘'].iloc[-6] - 1) * 100 if len(index_hist) >= 6 else 0
                    index_10d = (index_hist['收盘'].iloc[-1] / index_hist['收盘'].iloc[-11] - 1) * 100 if len(index_hist) >= 11 else 0
                    index_20d = (index_hist['收盘'].iloc[-1] / index_hist['收盘'].iloc[-21] - 1) * 100 if len(index_hist) >= 21 else 0

                    rs_5d = stock_5d - index_5d
                    rs_10d = stock_10d - index_10d
                    rs_20d = stock_20d - index_20d

                    # === 3. 强弱趋势判断 ===
                    # 分析近10天的表现
                    outperform_days = 0
                    for i in range(-10, 0):
                        if i-1 >= -len(stock_hist) and i-1 >= -len(index_hist):
                            stock_daily = (stock_hist['收盘'].iloc[i] / stock_hist['收盘'].iloc[i-1] - 1) * 100
                            index_daily = (index_hist['收盘'].iloc[i] / index_hist['收盘'].iloc[i-1] - 1) * 100

                            # 大盘涨时涨更多，或大盘跌时跌更少
                            if stock_daily > index_daily:
                                outperform_days += 1

                    trend_score = (outperform_days - 5) * 2  # -10到+10

            # === 综合相对强度评分 ===
            rs_score = 0

            # 当日超额收益评分
            if daily_excess > 3:
                rs_score += 10
            elif daily_excess > 2:
                rs_score += 7
            elif daily_excess > 1:
                rs_score += 5
            elif daily_excess > 0:
                rs_score += 3
            elif daily_excess > -1:
                rs_score += 0
            else:
                rs_score -= 5

            # 近期超额收益加分
            if rs_5d > 5:
                rs_score += 5
            elif rs_5d > 2:
                rs_score += 3
            elif rs_5d < -5:
                rs_score -= 5

            if rs_10d > 8:
                rs_score += 5
            elif rs_10d < -8:
                rs_score -= 5

            # 趋势评分加成
            rs_score += trend_score // 2

            # 限制范围
            rs_score = max(-15, min(15, rs_score))

            # 相对强度状态判定
            if rs_score >= 10:
                rs_status = "显著强势"
            elif rs_score >= 5:
                rs_status = "相对强势"
            elif rs_score >= 0:
                rs_status = "基本同步"
            elif rs_score >= -5:
                rs_status = "相对弱势"
            else:
                rs_status = "显著弱势"

            detail = {
                '当日超额': daily_excess,
                '5日超额': rs_5d,
                '10日超额': rs_10d,
                '20日超额': rs_20d,
                '跑赢天数': outperform_days if 'outperform_days' in dir() else 0,
                '沪深300涨幅': hs300_change,
                '上证涨幅': sh_change,
                '相对强度': rs_status,
                '相对强度得分': rs_score
            }

            return rs_score, detail

        except Exception as e:
            return 0, {'相对强度': '分析失败', '相对强度得分': 0}

    def analyze_price_position(self, stock_code, stock_name):
        """
        关键价格位置确认（v6.0新增）
        分析近半年至一年的走势，评估：
        1. 突破有效性：是否放量突破核心压力位
        2. 支撑稳固性：是否远离并站稳核心支撑位

        返回：(价格位置评分, 详细数据)
        """
        try:
            # 获取近一年的历史数据
            hist_data = self.get_historical_data(stock_code, days=250)

            if hist_data is None or len(hist_data) < 60:
                return 0, {'位置状态': '数据不足', '位置得分': 0}

            current_price = hist_data['收盘'].iloc[-1]
            current_volume = hist_data['成交量'].iloc[-1]

            # === 1. 识别关键价格位 ===
            # 近半年高点和低点
            half_year_high = hist_data['最高'].tail(120).max()
            half_year_low = hist_data['最低'].tail(120).min()

            # 近一年高点和低点（如果有足够数据）
            year_high = hist_data['最高'].max()
            year_low = hist_data['最低'].min()

            # 近期前高（20日高点）
            recent_high = hist_data['最高'].tail(20).max()
            # 近期前低（20日低点）
            recent_low = hist_data['最低'].tail(20).min()

            # 计算成交量均值
            vol_ma20 = hist_data['成交量'].tail(20).mean()

            # === 2. 识别密集成交区（近60日） ===
            recent_60 = hist_data.tail(60)
            # 简化：使用成交量加权平均价作为密集成交区中心
            vwap_60 = (recent_60['收盘'] * recent_60['成交量']).sum() / recent_60['成交量'].sum()

            # === 3. 突破有效性分析 ===
            breakthrough_score = 0
            breakthrough_status = ""

            # 判断是否突破半年高点
            if current_price >= half_year_high * 0.98:
                # 接近或突破半年高点
                if current_volume > vol_ma20 * 1.5:
                    # 放量突破
                    breakthrough_score = 10
                    breakthrough_status = "放量突破半年高点"
                elif current_volume > vol_ma20 * 1.2:
                    breakthrough_score = 7
                    breakthrough_status = "突破半年高点"
                else:
                    breakthrough_score = 3
                    breakthrough_status = "缩量触及高点(需确认)"
            elif current_price >= recent_high * 0.98:
                # 突破近期高点
                if current_volume > vol_ma20 * 1.3:
                    breakthrough_score = 6
                    breakthrough_status = "放量突破近期高点"
                else:
                    breakthrough_score = 3
                    breakthrough_status = "突破近期高点"
            elif current_price > vwap_60:
                # 站上密集成交区
                breakthrough_score = 2
                breakthrough_status = "站上密集成交区"
            else:
                breakthrough_score = -2
                breakthrough_status = "未突破压力位"

            # === 4. 支撑稳固性分析 ===
            support_score = 0
            support_status = ""

            # 计算距离支撑位的安全距离
            distance_from_half_year_low = (current_price - half_year_low) / half_year_low * 100
            distance_from_recent_low = (current_price - recent_low) / recent_low * 100

            # 距离半年低点的比例
            if distance_from_half_year_low > 50:
                support_score = 8
                support_status = "远离底部区域"
            elif distance_from_half_year_low > 30:
                support_score = 5
                support_status = "脱离底部"
            elif distance_from_half_year_low > 15:
                support_score = 2
                support_status = "离底部有距离"
            elif distance_from_half_year_low > 5:
                support_score = -2
                support_status = "接近底部支撑"
            else:
                support_score = -5
                support_status = "处于底部区域"

            # 判断是否处于震荡区间中部
            price_range = half_year_high - half_year_low
            if price_range > 0:
                position_ratio = (current_price - half_year_low) / price_range

                if 0.4 <= position_ratio <= 0.6:
                    # 处于震荡区间中部，趋势不明
                    support_score -= 3
                    support_status += "(震荡区间中部)"

            # === 5. 综合价格位置评分 ===
            position_score = breakthrough_score + support_score

            # 位置状态判定
            if position_score >= 15:
                position_status = "突破确认+支撑稳固"
            elif position_score >= 10:
                position_status = "位置良好"
            elif position_score >= 5:
                position_status = "位置一般"
            elif position_score >= 0:
                position_status = "位置中性"
            else:
                position_status = "位置不佳"

            detail = {
                '当前价': current_price,
                '半年高点': half_year_high,
                '半年低点': half_year_low,
                '近期高点': recent_high,
                '近期低点': recent_low,
                '距半年低点': f"{distance_from_half_year_low:.1f}%",
                '距半年高点': f"{(half_year_high - current_price) / half_year_high * 100:.1f}%",
                '突破状态': breakthrough_status,
                '支撑状态': support_status,
                '位置状态': position_status,
                '位置得分': position_score,
                '是否放量': current_volume > vol_ma20 * 1.3
            }

            return position_score, detail

        except Exception as e:
            return 0, {'位置状态': '分析失败', '位置得分': 0}

    def calculate_composite_score(self, fund_consistency, fund_flow_ratio, rs_score, position_score, original_signal_strength):
        """
        三维度综合评分系统（v6.0新增）

        理想强势标的需同时满足：
        1. 整体资金净流入与主力动向形成共振
        2. 走势强度明显超越大盘
        3. 股价已有效突破关键压力位并远离核心支撑区

        返回：(综合评分, 评级, 风险提示)
        """
        # 各维度权重
        weight_fund = 0.35      # 资金流向权重
        weight_rs = 0.30        # 相对强度权重
        weight_position = 0.25  # 价格位置权重
        weight_original = 0.10  # 原有信号权重

        # 资金维度得分（一致性 + 流量占比）
        fund_score = (fund_consistency + fund_flow_ratio) / 2

        # 归一化各维度得分到0-100
        fund_normalized = max(0, min(100, (fund_score + 10) * 5))
        rs_normalized = max(0, min(100, (rs_score + 15) * 3.33))
        position_normalized = max(0, min(100, (position_score + 10) * 4))
        original_normalized = max(0, min(100, original_signal_strength * 10))

        # 综合评分
        composite = (
            fund_normalized * weight_fund +
            rs_normalized * weight_rs +
            position_normalized * weight_position +
            original_normalized * weight_original
        )

        # 检查矛盾信号
        contradictions = []
        risk_level = 0

        # 资金与相对强度矛盾
        if fund_score > 5 and rs_score < -5:
            contradictions.append("资金流入但相对弱势")
            risk_level += 1
        if fund_score < -5 and rs_score > 5:
            contradictions.append("资金流出但相对强势")
            risk_level += 1

        # 相对强度与位置矛盾
        if rs_score > 5 and position_score < -3:
            contradictions.append("相对强势但位置不佳")
            risk_level += 1

        # 资金与位置矛盾
        if fund_score > 5 and position_score < -5:
            contradictions.append("资金流入但处于高压力区")
            risk_level += 1

        # 评级判定
        if composite >= 75 and risk_level == 0:
            rating = "AAA"
            rating_desc = "极强"
        elif composite >= 65 and risk_level <= 1:
            rating = "AA"
            rating_desc = "强势"
        elif composite >= 55 and risk_level <= 1:
            rating = "A"
            rating_desc = "良好"
        elif composite >= 45:
            rating = "B"
            rating_desc = "一般"
        elif composite >= 35:
            rating = "C"
            rating_desc = "较弱"
        else:
            rating = "D"
            rating_desc = "弱势"

        # 风险提示
        if risk_level >= 2:
            risk_warning = "⚠️ 多维度信号矛盾，建议保守"
        elif risk_level == 1:
            risk_warning = "⚡ 存在信号背离，需谨慎"
        else:
            risk_warning = "✅ 信号协同一致"

        return composite, f"{rating}({rating_desc})", risk_warning, contradictions

    def get_concept_stocks(self, concept_name):
        """获取概念板块成分股"""
        if concept_name in self.concept_stocks:
            return self.concept_stocks[concept_name]
        try:
            df = ak.stock_board_concept_cons_em(symbol=concept_name)
            codes = df['代码'].tolist() if not df.empty else []
            self.concept_stocks[concept_name] = codes
            return codes
        except:
            return []
    
    def get_industry_stocks(self, industry_name):
        """获取行业板块成分股"""
        try:
            df = ak.stock_board_industry_cons_em(symbol=industry_name)
            return df['代码'].tolist() if not df.empty else []
        except:
            return []
    
    def get_stock_concepts(self, stock_code):
        """获取个股所属概念板块"""
        try:
            df = ak.stock_individual_info_em(symbol=stock_code)
            if df is not None and not df.empty:
                industry_row = df[df['item'] == '行业']
                if not industry_row.empty:
                    return industry_row['value'].values[0]
        except:
            pass
        return ""
    
    def step1_filter_by_change_pct(self, df):
        """第一步：涨幅区间筛选 (0% ~ 5%)"""
        print("\n" + "-" * 50)
        print("【第一步】涨幅区间筛选: 0% ≤ 涨幅 ≤ 5%")

        df_filtered = df[(df['涨跌幅'] >= 0) & (df['涨跌幅'] <= 5)].copy()
        
        # 排除ST股票
        df_filtered = df_filtered[~df_filtered['名称'].str.contains('ST|退', na=False)]
        
        # 排除北交所股票
        df_filtered = df_filtered[~df_filtered['代码'].str.startswith(('8', '4'))]
        
        print(f"   ✅ 筛选后剩余: {len(df_filtered)} 只")
        return df_filtered

    def _calculate_monthly_gain(self, stock_code):
        """计算单只股票的月涨幅（供多线程调用）"""
        try:
            hist_data = self.get_historical_data(stock_code, days=35)

            if hist_data is None or len(hist_data) < 20:
                return stock_code, None, True  # 数据不足，保留

            # 计算近一个月涨幅（20个交易日）
            if len(hist_data) >= 21:
                price_20d_ago = hist_data['收盘'].iloc[-21]
            else:
                price_20d_ago = hist_data['收盘'].iloc[0]

            current_price = hist_data['收盘'].iloc[-1]
            monthly_gain = (current_price - price_20d_ago) / price_20d_ago * 100

            return stock_code, monthly_gain, monthly_gain < 30

        except Exception as e:
            return stock_code, None, True  # 出错时保守处理，保留

    def step1b_filter_by_monthly_gain(self, df):
        """第1.5步：月涨幅筛选 (近一个月涨幅 < 30%) - 多线程优化版"""
        print("\n" + "-" * 50)
        print("【第1.5步】月涨幅筛选: 近一个月涨幅 < 30%")
        print("   💡 目的: 排除短期涨幅过大的股票，避免追高")
        print("   ⚡ 使用多线程加速处理")

        if df.empty:
            return df

        stock_codes = df['代码'].tolist()
        total = len(stock_codes)
        print(f"\n   ⏳ 正在并行计算 {total} 只股票的月涨幅...")

        # 存储结果：{stock_code: (monthly_gain, is_qualified)}
        results = {}
        completed = 0

        # 使用线程池并行处理（限制并发数避免API限流）
        max_workers = min(20, total)  # 最多20个并发线程

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_code = {
                executor.submit(self._calculate_monthly_gain, code): code
                for code in stock_codes
            }

            # 收集结果
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                try:
                    stock_code, monthly_gain, is_qualified = future.result()
                    results[stock_code] = (monthly_gain, is_qualified)
                except Exception as e:
                    results[code] = (None, True)  # 出错保留

                completed += 1
                if completed % 100 == 0 or completed == total:
                    print(f"   ⏳ 已完成 {completed}/{total} ({completed*100//total}%)")

        # 根据结果筛选
        qualified_stocks = []
        for idx, row in df.iterrows():
            stock_code = row['代码']
            monthly_gain, is_qualified = results.get(stock_code, (None, True))

            if is_qualified:
                row_copy = row.copy()
                row_copy['月涨幅'] = monthly_gain
                qualified_stocks.append(row_copy)

        df_filtered = pd.DataFrame(qualified_stocks)

        excluded_count = len(df) - len(df_filtered)
        print(f"\n   ✅ 筛选后剩余: {len(df_filtered)} 只")
        if excluded_count > 0:
            print(f"   ⚠️ 已排除 {excluded_count} 只月涨幅≥30%的股票")

        return df_filtered

    def step2_filter_by_volume_ratio(self, df):
        """第二步：量比筛选 (量比 >= 1)"""
        print("\n" + "-" * 50)
        print("【第二步】热度筛选: 量比 ≥ 1")
        
        df_filtered = df[df['量比'] >= 1].copy()
        
        print(f"   ✅ 筛选后剩余: {len(df_filtered)} 只")
        return df_filtered
    
    def step3_filter_by_turnover(self, df):
        """第三步：换手率筛选 (5% ~ 10%)"""
        print("\n" + "-" * 50)
        print("【第三步】活跃度筛选: 5% ≤ 换手率 ≤ 10%")
        
        df_filtered = df[(df['换手率'] >= 5) & (df['换手率'] <= 10)].copy()
        
        print(f"   ✅ 筛选后剩余: {len(df_filtered)} 只")
        return df_filtered
    
    def step4_filter_by_market_cap(self, df):
        """第四步：流通市值筛选 (50亿 ~ 200亿)"""
        print("\n" + "-" * 50)
        print("【第四步】规模筛选: 50亿 ≤ 流通市值 ≤ 200亿")
        
        df['流通市值_亿'] = df['流通市值'] / 1e8
        df_filtered = df[(df['流通市值_亿'] >= 50) & (df['流通市值_亿'] <= 200)].copy()
        
        print(f"   ✅ 筛选后剩余: {len(df_filtered)} 只")
        return df_filtered
    
    def get_historical_data(self, stock_code, days=30):
        """获取个股历史K线数据"""
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days+30)).strftime('%Y%m%d')
            
            df = ak.stock_zh_a_hist(
                symbol=stock_code, 
                period="daily",
                start_date=start_date, 
                end_date=end_date,
                adjust="qfq"
            )
            return df
        except:
            return None
    
    def step5_filter_by_fund_flow(self, df):
        """
        第五步：资金流向筛选（v6.0升级）
        核心逻辑：
        1. 剔除主力资金流出的股票（看跌信号）
        2. 优选超大单和大单流入的股票（看涨信号）
        3. 【v6.0新增】资金一致性分析 + 流量占比评估
        """
        print("\n" + "-" * 50)
        print("【第五步】💰 资金流向深度分析（v6.0升级版）")
        print("   ⚡ 策略升级: 主力信号 + 资金一致性 + 流量占比")

        if df.empty:
            return df

        # 预先获取所有资金流向数据（避免循环中重复调用）
        self.get_all_fund_flow_data()

        qualified_stocks = []
        fund_signals = []

        print(f"\n   ⏳ 正在分析 {len(df)} 只股票的资金流向...")

        processed_count = 0

        for idx, row in df.iterrows():
            stock_code = row['代码']
            stock_name = row['名称']
            turnover_amount = row.get('成交额', 0)

            processed_count += 1
            if processed_count % 10 == 0:
                print(f"   ⏳ 已处理 {processed_count}/{len(df)} 只...")

            # 分析资金流向信号（原有逻辑）
            signal_type, signal_strength, detail = self.analyze_fund_flow_signal(stock_code, stock_name)

            # 【v6.0新增】资金一致性和流量占比分析
            consistency_score, flow_ratio_score, depth_detail = self.analyze_fund_flow_depth(
                stock_code, stock_name, turnover_amount
            )

            # 如果无法获取资金流向数据，默认保留（赋予NEUTRAL信号）
            if signal_type == 'UNKNOWN':
                row_copy = row.copy()
                row_copy['资金信号'] = 'NEUTRAL'
                row_copy['信号强度'] = 0
                row_copy['主力净流入'] = 0
                row_copy['主力占比'] = 0
                row_copy['超大单净流入'] = 0
                row_copy['超大单占比'] = 0
                row_copy['资金一致性'] = '未知'
                row_copy['一致性得分'] = 0
                row_copy['流量占比'] = 0
                row_copy['流量占比得分'] = 0
                qualified_stocks.append(row_copy)
                fund_signals.append('NEUTRAL')
                continue

            # 剔除强烈看跌和看跌信号的股票
            if signal_type in ['STRONG_SELL', 'SELL']:
                continue

            # 【v6.0新增】如果资金一致性为"一致流出"，也剔除
            if depth_detail.get('一致性') == '一致流出':
                continue

            # 保留看涨、强烈看涨、中性信号的股票
            if signal_type in ['STRONG_BUY', 'BUY', 'NEUTRAL']:
                row_copy = row.copy()
                row_copy['资金信号'] = signal_type
                row_copy['信号强度'] = signal_strength
                row_copy['主力净流入'] = detail.get('主力净流入', 0)
                row_copy['主力占比'] = detail.get('主力占比', 0)
                row_copy['超大单净流入'] = detail.get('超大单净流入', 0)
                row_copy['超大单占比'] = detail.get('超大单占比', 0)
                # v6.0新增字段
                row_copy['资金一致性'] = depth_detail.get('一致性', '未知')
                row_copy['一致性得分'] = consistency_score
                row_copy['整体净流入'] = depth_detail.get('整体净流入', 0)
                row_copy['散户净流入'] = depth_detail.get('散户净流入', 0)
                row_copy['流量占比'] = depth_detail.get('流量占比', 0)
                row_copy['流量占比得分'] = flow_ratio_score
                qualified_stocks.append(row_copy)
                fund_signals.append(signal_type)

        df_filtered = pd.DataFrame(qualified_stocks)

        # 统计信号分布
        if not df_filtered.empty:
            strong_buy_count = fund_signals.count('STRONG_BUY')
            buy_count = fund_signals.count('BUY')
            neutral_count = fund_signals.count('NEUTRAL')

            # 统计资金一致性
            strong_consistency = len(df_filtered[df_filtered['资金一致性'] == '强一致流入'])
            absorption = len(df_filtered[df_filtered['资金一致性'] == '主力吸筹'])

            print(f"\n   ✅ 筛选后剩余: {len(df_filtered)} 只")
            print(f"   📊 信号分布: 强烈看涨={strong_buy_count} | 看涨={buy_count} | 中性={neutral_count}")
            print(f"   💎 资金一致性: 强一致流入={strong_consistency} | 主力吸筹={absorption}")
            if strong_buy_count > 0:
                print(f"   ⭐ 发现 {strong_buy_count} 只【超大单往里冲】的强势股！")
        else:
            print(f"   ✅ 筛选后剩余: 0 只")

        return df_filtered
    
    def step6_filter_by_volume_pattern(self, df):
        """第六步：成交量形态筛选 (台阶式稳步放大)"""
        print("\n" + "-" * 50)
        print("【第六步】动能确认: 成交量台阶式放大")
        
        if df.empty:
            return df
        
        qualified_stocks = []
        
        for idx, row in df.iterrows():
            stock_code = row['代码']
            
            hist_data = self.get_historical_data(stock_code)
            if hist_data is None or len(hist_data) < 10:
                continue
            
            recent_volumes = hist_data['成交量'].tail(10).values
            
            if len(recent_volumes) >= 10:
                first_half_avg = np.mean(recent_volumes[:5])
                second_half_avg = np.mean(recent_volumes[5:])
                
                if first_half_avg > 0:
                    volume_increase = (second_half_avg - first_half_avg) / first_half_avg
                    volume_volatility = np.std(recent_volumes) / np.mean(recent_volumes)
                    
                    if volume_increase > 0.1 and volume_volatility < 0.8:
                        qualified_stocks.append(row)
        
        df_filtered = pd.DataFrame(qualified_stocks)
        print(f"   ✅ 筛选后剩余: {len(df_filtered)} 只")
        return df_filtered
    
    def step7_filter_by_ma_trend(self, df):
        """第七步：趋势确认 (均线多头排列)"""
        print("\n" + "-" * 50)
        print("【第七步】趋势确认: 均线多头排列 (MA5>MA10>MA20, 股价>MA60)")
        
        if df.empty:
            return df
            
        qualified_stocks = []
        
        for idx, row in df.iterrows():
            stock_code = row['代码']
            
            hist_data = self.get_historical_data(stock_code, days=90)
            if hist_data is None or len(hist_data) < 60:
                continue
            
            hist_data['MA5'] = hist_data['收盘'].rolling(window=5).mean()
            hist_data['MA10'] = hist_data['收盘'].rolling(window=10).mean()
            hist_data['MA20'] = hist_data['收盘'].rolling(window=20).mean()
            hist_data['MA60'] = hist_data['收盘'].rolling(window=60).mean()
            
            latest = hist_data.iloc[-1]
            
            ma_bullish = (latest['MA5'] > latest['MA10'] > latest['MA20'])
            above_ma60 = latest['收盘'] > latest['MA60']
            
            if latest['MA20'] > 0:
                ma_spread = (latest['MA5'] - latest['MA20']) / latest['MA20']
                ma_diverging = ma_spread > 0.02
            else:
                ma_diverging = False
            
            if ma_bullish and above_ma60 and ma_diverging:
                qualified_stocks.append(row)
        
        df_filtered = pd.DataFrame(qualified_stocks)
        print(f"   ✅ 筛选后剩余: {len(df_filtered)} 只")
        return df_filtered
    
    def step8_filter_by_intraday_strength(self, df):
        """第八步：强度确认 (分时图强度)"""
        print("\n" + "-" * 50)
        print("【第八步】强度确认: 分时走势强于大盘")
        
        if df.empty:
            return df
        
        try:
            index_data = ak.stock_zh_index_spot_em()
            sh_index = index_data[index_data['代码'] == '000001']
            if not sh_index.empty:
                market_change = sh_index['涨跌幅'].values[0]
            else:
                market_change = 0
        except:
            market_change = 0
        
        qualified_stocks = []
        
        for idx, row in df.iterrows():
            stock_change = row['涨跌幅']
            if stock_change > market_change + 2:
                qualified_stocks.append(row)
        
        df_filtered = pd.DataFrame(qualified_stocks)
        print(f"   ✅ 筛选后剩余: {len(df_filtered)} 只")
        print(f"   📈 今日大盘涨幅: {market_change:.2f}%")
        return df_filtered
    
    def step9_filter_by_win_rate(self, df):
        """第九步：胜率筛选 (近60个交易日上涨天数>下跌天数)"""
        print("\n" + "-" * 50)
        print("【第九步】胜率筛选: 近60个交易日上涨天数 > 下跌天数")
        
        if df.empty:
            return df
        
        qualified_stocks = []
        
        for idx, row in df.iterrows():
            stock_code = row['代码']
            
            hist_data = self.get_historical_data(stock_code, days=90)
            if hist_data is None or len(hist_data) < 60:
                continue
            
            # 取最近60个交易日
            recent_60_days = hist_data.tail(60)
            
            # 计算涨跌情况
            recent_60_days['涨跌'] = recent_60_days['收盘'] - recent_60_days['开盘']
            
            up_days = len(recent_60_days[recent_60_days['涨跌'] > 0])
            down_days = len(recent_60_days[recent_60_days['涨跌'] < 0])
            
            # 上涨天数大于下跌天数
            if up_days > down_days:
                row_copy = row.copy()
                row_copy['上涨天数'] = up_days
                row_copy['下跌天数'] = down_days
                row_copy['胜率'] = f"{up_days}/{down_days}"
                qualified_stocks.append(row_copy)
        
        df_filtered = pd.DataFrame(qualified_stocks)
        if not df_filtered.empty:
            print(f"   ✅ 筛选后剩余: {len(df_filtered)} 只")
            avg_up = df_filtered['上涨天数'].mean() if '上涨天数' in df_filtered.columns else 0
            print(f"   📊 平均上涨天数: {avg_up:.1f} 天")
        else:
            print(f"   ✅ 筛选后剩余: 0 只")
        
        return df_filtered
    
    def step10_theme_scoring(self, df):
        """第十步：主题加分"""
        print("\n" + "-" * 50)

        if self.target_sector:
            print(f"【第十步】板块标识: 标注所属板块【{self.target_sector}】")
        else:
            print(f"【第十步】主题加分: 匹配{self.current_month}月【{self.theme.get('name', '')}】主题")

        if df.empty:
            return df

        # 为每只股票计算主题匹配分数
        theme_scores = []
        matched_themes = []

        for idx, row in df.iterrows():
            stock_code = row['代码']
            stock_name = row['名称']

            score = 0
            matched = []

            # 如果指定了目标板块，直接标注
            if self.target_sector:
                matched.append(f"板块:{self.target_sector}")
                score = 10
            else:
                # 检查股票名称是否包含主题关键词
                for keyword in self.theme.get('keywords', []):
                    if keyword in stock_name:
                        score += 10
                        matched.append(keyword)

                # 获取股票所属行业进行匹配
                try:
                    industry = self.get_stock_concepts(stock_code)
                    for keyword in self.theme.get('keywords', []):
                        if keyword in industry:
                            score += 5
                            if keyword not in matched:
                                matched.append(f"行业:{industry}")
                            break
                except:
                    pass

            theme_scores.append(score)
            matched_themes.append(", ".join(matched) if matched else "无直接匹配")

        df = df.copy()
        df['主题得分'] = theme_scores
        df['匹配主题'] = matched_themes

        # 按资金信号强度、主题得分、涨跌幅排序
        df = df.sort_values(['信号强度', '主题得分', '涨跌幅'], ascending=[False, False, False])

        theme_matched = len(df[df['主题得分'] > 0])
        if self.target_sector:
            print(f"   ✅ 所有 {len(df)} 只股票均属于【{self.target_sector}】板块")
        else:
            print(f"   ✅ 其中 {theme_matched} 只匹配当月主题")

        return df

    def step11_multidimensional_analysis(self, df):
        """
        第十一步：三维度综合分析（v6.0新增核心步骤）
        整合：资金共振 + 市场相对强度 + 关键价格位置
        """
        print("\n" + "-" * 50)
        print("【第十一步】🎯 三维度综合分析（v6.0核心升级）")
        print("   📊 维度1: 资金共振（主力+整体一致性）")
        print("   📈 维度2: 市场相对强度（跑赢大盘）")
        print("   📍 维度3: 关键价格位置（突破+支撑）")

        if df.empty:
            return df

        print(f"\n   ⏳ 正在进行 {len(df)} 只股票的三维度深度分析...")

        qualified_stocks = []
        processed_count = 0

        for idx, row in df.iterrows():
            stock_code = row['代码']
            stock_name = row['名称']
            current_change = row['涨跌幅']

            processed_count += 1
            if processed_count % 5 == 0:
                print(f"   ⏳ 已完成 {processed_count}/{len(df)} 只...")

            # === 维度2：市场相对强度分析 ===
            rs_score, rs_detail = self.analyze_relative_strength(stock_code, stock_name, current_change)

            # === 维度3：关键价格位置分析 ===
            position_score, position_detail = self.analyze_price_position(stock_code, stock_name)

            # === 综合评分 ===
            fund_consistency = row.get('一致性得分', 0)
            fund_flow_ratio = row.get('流量占比得分', 0)
            original_signal_strength = row.get('信号强度', 0)

            composite_score, rating, risk_warning, contradictions = self.calculate_composite_score(
                fund_consistency, fund_flow_ratio, rs_score, position_score, original_signal_strength
            )

            # 构建结果行
            row_copy = row.copy()
            # 相对强度字段
            row_copy['相对强度'] = rs_detail.get('相对强度', '未知')
            row_copy['相对强度得分'] = rs_score
            row_copy['当日超额'] = rs_detail.get('当日超额', 0)
            row_copy['5日超额'] = rs_detail.get('5日超额', 0)
            row_copy['沪深300涨幅'] = rs_detail.get('沪深300涨幅', 0)
            # 价格位置字段
            row_copy['位置状态'] = position_detail.get('位置状态', '未知')
            row_copy['位置得分'] = position_score
            row_copy['突破状态'] = position_detail.get('突破状态', '')
            row_copy['支撑状态'] = position_detail.get('支撑状态', '')
            row_copy['距半年高点'] = position_detail.get('距半年高点', '')
            row_copy['距半年低点'] = position_detail.get('距半年低点', '')
            row_copy['是否放量'] = position_detail.get('是否放量', False)
            # 综合评分字段
            row_copy['综合评分'] = composite_score
            row_copy['综合评级'] = rating
            row_copy['风险提示'] = risk_warning
            row_copy['矛盾信号'] = '|'.join(contradictions) if contradictions else ''

            qualified_stocks.append(row_copy)

        df_result = pd.DataFrame(qualified_stocks)

        if not df_result.empty:
            # 按综合评分排序
            df_result = df_result.sort_values('综合评分', ascending=False)

            # 统计评级分布
            aaa_count = len(df_result[df_result['综合评级'].str.startswith('AAA')])
            aa_count = len(df_result[df_result['综合评级'].str.startswith('AA') & ~df_result['综合评级'].str.startswith('AAA')])
            a_count = len(df_result[df_result['综合评级'].str.startswith('A') & ~df_result['综合评级'].str.startswith('AA')])

            # 统计相对强度
            strong_rs = len(df_result[df_result['相对强度'].isin(['显著强势', '相对强势'])])

            # 统计价格位置
            good_position = len(df_result[df_result['位置状态'].isin(['突破确认+支撑稳固', '位置良好'])])

            print(f"\n   ✅ 三维度分析完成: {len(df_result)} 只")
            print(f"   🏆 综合评级: AAA={aaa_count} | AA={aa_count} | A={a_count}")
            print(f"   📈 相对强势: {strong_rs} 只跑赢大盘")
            print(f"   📍 位置良好: {good_position} 只处于有利位置")

            if aaa_count > 0:
                print(f"   ⭐⭐⭐ 发现 {aaa_count} 只【三维共振】顶级标的！")
        else:
            print(f"   ✅ 分析完成: 0 只")

        return df_result
    
    def run(self, sector_codes=None):
        """执行完整筛选流程"""
        self.print_header()
        
        # 获取实时数据
        df = self.get_realtime_data(sector_codes)
        if df is None or df.empty:
            print("\n❌ 无法获取数据或板块内无股票，程序退出")
            return
        
        # 第一步：涨幅筛选
        df = self.step1_filter_by_change_pct(df)
        if df.empty:
            self.output_result(pd.DataFrame())
            return

        # 第1.5步：月涨幅筛选（排除短期涨幅过大的股票）
        df = self.step1b_filter_by_monthly_gain(df)
        if df.empty:
            self.output_result(pd.DataFrame())
            return

        # 第二步：量比筛选
        df = self.step2_filter_by_volume_ratio(df)
        if df.empty:
            self.output_result(pd.DataFrame())
            return
        
        # 第三步：换手率筛选
        df = self.step3_filter_by_turnover(df)
        if df.empty:
            self.output_result(pd.DataFrame())
            return
        
        # 第四步：流通市值筛选
        df = self.step4_filter_by_market_cap(df)
        if df.empty:
            self.output_result(pd.DataFrame())
            return
        
        # 第五步：资金流向筛选（新增核心步骤）
        df = self.step5_filter_by_fund_flow(df)
        if df.empty:
            self.output_result(pd.DataFrame())
            return
        
        print(f"\n⏳ 正在分析 {len(df)} 只股票的历史数据，请稍候...")
        
        # 第六步：成交量形态筛选
        df = self.step6_filter_by_volume_pattern(df)
        if df.empty:
            self.output_result(pd.DataFrame())
            return
        
        # 第七步：均线趋势筛选
        df = self.step7_filter_by_ma_trend(df)
        if df.empty:
            self.output_result(pd.DataFrame())
            return
        
        # 第八步：分时强度筛选
        df = self.step8_filter_by_intraday_strength(df)
        if df.empty:
            self.output_result(pd.DataFrame())
            return
        
        # 第九步：胜率筛选
        df = self.step9_filter_by_win_rate(df)
        if df.empty:
            self.output_result(pd.DataFrame())
            return
        
        # 第十步：主题加分
        df = self.step10_theme_scoring(df)

        # 第十一步：三维度综合分析（v6.0新增）
        df = self.step11_multidimensional_analysis(df)

        # 输出结果
        self.output_result(df)
    
    def output_result(self, df):
        """输出筛选结果（v6.0升级版 - 三维度展示）"""
        print("\n" + "=" * 70)
        print("【筛选结果】v6.0 三维度综合分析")
        print("=" * 70)

        if df.empty:
            print("\n🔴 今日暂无符合条件的标的")
            print("\n💡 提示: 严格遵循首要原则 - 无标的满足则当日放弃，不强行开仓")
        else:
            sector_info = f"【{self.target_sector}】板块内" if self.target_sector else ""
            print(f"\n🟢 {sector_info}共筛选出 {len(df)} 只潜在次日冲高标的")

            # 按综合评级分类显示
            aaa_stocks = df[df['综合评级'].str.startswith('AAA')]
            aa_stocks = df[df['综合评级'].str.startswith('AA') & ~df['综合评级'].str.startswith('AAA')]
            a_stocks = df[df['综合评级'].str.startswith('A') & ~df['综合评级'].str.startswith('AA')]
            other_stocks = df[~df['综合评级'].str.startswith('A')]

            # 1. 显示AAA级标的（三维共振）
            if not aaa_stocks.empty:
                print(f"\n{'='*60}")
                print(f"⭐⭐⭐ 【AAA级 - 三维共振顶级标的】({len(aaa_stocks)}只)")
                print(f"{'='*60}")

                for idx, row in aaa_stocks.iterrows():
                    self._print_stock_detail(row, level='AAA')

            # 2. 显示AA级标的
            if not aa_stocks.empty:
                print(f"\n{'='*60}")
                print(f"⭐⭐ 【AA级 - 强势标的】({len(aa_stocks)}只)")
                print(f"{'='*60}")

                for idx, row in aa_stocks.iterrows():
                    self._print_stock_detail(row, level='AA')

            # 3. 显示A级标的
            if not a_stocks.empty:
                print(f"\n{'='*60}")
                print(f"⭐ 【A级 - 良好标的】({len(a_stocks)}只)")
                print(f"{'='*60}")

                for idx, row in a_stocks.iterrows():
                    self._print_stock_detail(row, level='A')

            # 4. 显示其他标的（B/C/D级）
            if not other_stocks.empty:
                print(f"\n{'='*60}")
                print(f"📋 【B/C/D级 - 观察标的】({len(other_stocks)}只)")
                print(f"{'='*60}")

                for idx, row in other_stocks.head(5).iterrows():  # 只显示前5只
                    self._print_stock_detail(row, level='other')

                if len(other_stocks) > 5:
                    print(f"\n   ... 还有 {len(other_stocks) - 5} 只，建议谨慎观察")

            # 输出股票代码汇总
            print("\n" + "-" * 60)
            print("📋 股票代码汇总（按综合评级排序）:")

            if not aaa_stocks.empty:
                print(f"   ⭐⭐⭐ AAA级: {', '.join(aaa_stocks['代码'].tolist())}")
            if not aa_stocks.empty:
                print(f"   ⭐⭐ AA级: {', '.join(aa_stocks['代码'].tolist())}")
            if not a_stocks.empty:
                print(f"   ⭐ A级: {', '.join(a_stocks['代码'].tolist())}")

            # 三维度综合建议
            print("\n" + "-" * 60)
            print("💡 【v6.0 三维度操作建议】")

            print("\n   📊 维度1 - 资金共振:")
            strong_consistency = df[df['资金一致性'] == '强一致流入']
            if not strong_consistency.empty:
                print(f"      ✅ 发现 {len(strong_consistency)} 只【强一致流入】标的")
                print(f"         → 主力与整体资金同向流入，最佳买入信号")
            absorption = df[df['资金一致性'] == '主力吸筹']
            if not absorption.empty:
                print(f"      📈 发现 {len(absorption)} 只【主力吸筹】标的")
                print(f"         → 主力逆势买入，关注后续放量")

            print("\n   📈 维度2 - 相对强度:")
            strong_rs = df[df['相对强度'].isin(['显著强势', '相对强势'])]
            if not strong_rs.empty:
                print(f"      ✅ 发现 {len(strong_rs)} 只【跑赢大盘】标的")
                avg_excess = strong_rs['当日超额'].mean()
                print(f"         → 平均超额收益: {avg_excess:.2f}%")
            weak_rs = df[df['相对强度'].isin(['相对弱势', '显著弱势'])]
            if not weak_rs.empty:
                print(f"      ⚠️ 有 {len(weak_rs)} 只相对弱势，需警惕")

            print("\n   📍 维度3 - 价格位置:")
            good_position = df[df['位置状态'].isin(['突破确认+支撑稳固', '位置良好'])]
            if not good_position.empty:
                print(f"      ✅ 发现 {len(good_position)} 只【位置良好】标的")
                breakthrough = df[df['突破状态'].str.contains('突破', na=False)]
                if not breakthrough.empty:
                    print(f"         → 其中 {len(breakthrough)} 只已突破关键压力位")

            # 风险提示
            print("\n   ⚠️ 风险警示:")
            contradiction_stocks = df[df['矛盾信号'] != '']
            if not contradiction_stocks.empty:
                print(f"      → 有 {len(contradiction_stocks)} 只存在信号矛盾，建议保守对待")
                for idx, row in contradiction_stocks.head(3).iterrows():
                    print(f"         {row['代码']} {row['名称']}: {row['矛盾信号']}")

            print("\n   【操作要点】")
            print("   1. 优先关注AAA/AA级标的，三维度信号协同一致")
            print("   2. 次日竞价阶段确认资金是否持续流入")
            print("   3. 确认个股相对大盘是否保持强势")
            print("   4. 关注突破后的量价配合和支撑位有效性")
            print("   5. 若三维度出现矛盾信号，建议放弃或减仓")

            if self.current_month == 4:
                print("\n   ⚠️ 4月年报季警示: 注意规避业绩雷，建议轻仓观望!")

        print("\n" + "=" * 70)
        print("⚠️  风险提示: 本筛选仅供参考，不构成投资建议")
        print("    v6.0 三维度分析旨在降低风险，但不能完全规避")
        print("    投资有风险，入市需谨慎")
        print("=" * 70)

    def _print_stock_detail(self, row, level='A'):
        """打印个股详细信息"""
        # 根据级别选择图标
        icons = {
            'AAA': '🔥',
            'AA': '📈',
            'A': '📌',
            'other': '📋'
        }
        icon = icons.get(level, '📋')

        print(f"\n  {icon} {row['代码']} | {row['名称']} | 综合评级: {row['综合评级']} | 评分: {row['综合评分']:.1f}")

        # 基础数据
        print(f"     📊 涨幅: {row['涨跌幅']:.2f}% | 量比: {row['量比']:.2f} | "
              f"换手率: {row['换手率']:.2f}% | 流通市值: {row['流通市值_亿']:.1f}亿")

        # 资金流向（维度1）
        consistency = row.get('资金一致性', '未知')
        main_flow = row.get('主力净流入', 0) / 1e8
        flow_ratio = row.get('流量占比', 0)
        print(f"     💰 资金共振: {consistency} | 主力净流入: {main_flow:.2f}亿 | 流量占比: {flow_ratio:.1f}%")

        # 相对强度（维度2）
        rs_status = row.get('相对强度', '未知')
        daily_excess = row.get('当日超额', 0)
        rs_5d = row.get('5日超额', 0)
        hs300_change = row.get('沪深300涨幅', 0)
        print(f"     📈 相对强度: {rs_status} | 当日超额: {daily_excess:+.2f}% | 5日超额: {rs_5d:+.2f}% (沪深300: {hs300_change:.2f}%)")

        # 价格位置（维度3）
        position_status = row.get('位置状态', '未知')
        breakthrough = row.get('突破状态', '')
        support = row.get('支撑状态', '')
        is_volume = "放量" if row.get('是否放量', False) else "缩量"
        print(f"     📍 价格位置: {position_status} | {breakthrough} | {support} | {is_volume}")

        # 风险提示
        risk = row.get('风险提示', '')
        if risk and not risk.startswith('✅'):
            print(f"     {risk}")

        # 胜率信息（如果有）
        if '胜率' in row and pd.notna(row.get('胜率')):
            print(f"     📊 60日胜率: {row['胜率']} (上涨{row['上涨天数']}天 vs 下跌{row['下跌天数']}天)")

        # 主题匹配
        if row.get('主题得分', 0) > 0:
            print(f"     🎯 {row['匹配主题']}")


def show_monthly_calendar():
    """显示全年月份主题日历"""
    print("\n" + "=" * 70)
    print("📅 【A股全年月份主题日历】")
    print("=" * 70)
    
    for month, theme in MONTHLY_THEMES.items():
        status = "👈 当前" if month == datetime.now().month else ""
        print(f"\n{month:2d}月 | 🎯 {theme['name']:10s} | {theme['logic'][:35]}... {status}")
    
    print("\n" + "=" * 70)


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("【A股次日冲高标的筛选系统 v6.0】")
    print("  🆕 三维度综合分析: 资金共振 + 相对强度 + 关键价格位置")
    print("=" * 70)
    print("\n请选择操作:")
    print("  1. 全市场筛选（默认）- 三维度综合分析")
    print("  2. 指定板块/概念筛选 - 三维度综合分析")
    print("  3. 查看所有概念板块")
    print("  4. 查看所有行业板块")
    print("  5. 查看全年主题日历")
    
    try:
        choice = input("\n请输入选项 (1/2/3/4/5，回车默认1): ").strip()
    except:
        choice = "1"
    
    if not choice:
        choice = "1"
    
    if choice == "5":
        show_monthly_calendar()
    elif choice == "3":
        screener = StockScreener()
        screener.list_all_concepts()
    elif choice == "4":
        screener = StockScreener()
        screener.list_all_industries()
    elif choice == "2":
        # 指定板块筛选
        sector_name = input("\n请输入板块/概念名称（如：人工智能、新能源、半导体等）: ").strip()
        if not sector_name:
            print("❌ 板块名称不能为空")
            return
        
        screener = StockScreener(target_sector=sector_name)
        sector_codes, sector_type = screener.get_sector_stocks(sector_name)
        
        if not sector_codes:
            print("\n💡 提示: 请先使用选项3或4查看可用的板块/概念列表")
            return
        
        screener.run(sector_codes=sector_codes)
    else:
        # 全市场筛选
        screener = StockScreener()
        screener.run()


if __name__ == "__main__":
    main()
