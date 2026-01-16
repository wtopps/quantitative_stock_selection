#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股次日冲高标的筛选脚本 v5.0
基于量化条件 + 月份主题 + 形态分析 + 主力资金流向
新增：
1. 超大单和大单资金流向监控，精准捕捉主力意图
2. 指定板块/概念筛选功能，支持自定义板块选股
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
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
        
    def print_header(self):
        """打印头部信息"""
        print("=" * 70)
        print("【A股次日冲高标的筛选系统 v5.0】")
        print(f"筛选日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("🆕 新增功能: 超大单/大单资金流向监控 + 指定板块筛选")
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
        """第一步：涨幅区间筛选 (3% ~ 5%)"""
        print("\n" + "-" * 50)
        print("【第一步】涨幅区间筛选: 3% ≤ 涨幅 ≤ 5%")
        
        df_filtered = df[(df['涨跌幅'] >= 3) & (df['涨跌幅'] <= 5)].copy()
        
        # 排除ST股票
        df_filtered = df_filtered[~df_filtered['名称'].str.contains('ST|退', na=False)]
        
        # 排除北交所股票
        df_filtered = df_filtered[~df_filtered['代码'].str.startswith(('8', '4'))]
        
        print(f"   ✅ 筛选后剩余: {len(df_filtered)} 只")
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
        第五步：资金流向筛选（新增）
        核心逻辑：
        1. 剔除主力资金流出的股票（看跌信号）
        2. 优选超大单和大单流入的股票（看涨信号）
        """
        print("\n" + "-" * 50)
        print("【第五步】💰 资金流向筛选: 主力资金监控")
        print("   ⚡ 核心策略: 超大单往里冲=看涨，超大单和大单要跑=剔除")
        
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
            
            processed_count += 1
            if processed_count % 10 == 0:
                print(f"   ⏳ 已处理 {processed_count}/{len(df)} 只...")
            
            # 分析资金流向信号
            signal_type, signal_strength, detail = self.analyze_fund_flow_signal(stock_code, stock_name)
            
            # 如果无法获取资金流向数据，默认保留（赋予NEUTRAL信号）
            if signal_type == 'UNKNOWN':
                row_copy = row.copy()
                row_copy['资金信号'] = 'NEUTRAL'
                row_copy['信号强度'] = 0
                row_copy['主力净流入'] = 0
                row_copy['主力占比'] = 0
                row_copy['超大单净流入'] = 0
                row_copy['超大单占比'] = 0
                qualified_stocks.append(row_copy)
                fund_signals.append('NEUTRAL')
                continue
            
            # 剔除强烈看跌和看跌信号的股票
            if signal_type in ['STRONG_SELL', 'SELL']:
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
                qualified_stocks.append(row_copy)
                fund_signals.append(signal_type)
        
        df_filtered = pd.DataFrame(qualified_stocks)
        
        # 统计信号分布
        if not df_filtered.empty:
            strong_buy_count = fund_signals.count('STRONG_BUY')
            buy_count = fund_signals.count('BUY')
            neutral_count = fund_signals.count('NEUTRAL')
            
            print(f"\n   ✅ 筛选后剩余: {len(df_filtered)} 只")
            print(f"   📊 信号分布: 强烈看涨={strong_buy_count} | 看涨={buy_count} | 中性={neutral_count}")
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
        
        # 输出结果
        self.output_result(df)
    
    def output_result(self, df):
        """输出筛选结果"""
        print("\n" + "=" * 70)
        print("【筛选结果】")
        print("=" * 70)
        
        if df.empty:
            print("\n🔴 今日暂无符合条件的标的")
            print("\n💡 提示: 严格遵循首要原则 - 无标的满足则当日放弃，不强行开仓")
        else:
            # 分类显示：超大单强势 + 主题匹配 + 其他
            strong_buy = df[df['资金信号'] == 'STRONG_BUY']
            buy = df[df['资金信号'] == 'BUY']
            neutral = df[df['资金信号'] == 'NEUTRAL']
            
            sector_info = f"【{self.target_sector}】板块内" if self.target_sector else ""
            print(f"\n🟢 {sector_info}共筛选出 {len(df)} 只潜在次日冲高标的")
            
            # 1. 显示超大单强势股（最优先）
            if not strong_buy.empty:
                print(f"\n{'='*50}")
                print(f"⭐⭐⭐ 【超大单往里冲 - 强烈看涨】({len(strong_buy)}只)")
                print(f"{'='*50}")
                
                for idx, row in strong_buy.iterrows():
                    print(f"\n  🔥 {row['代码']} | {row['名称']}")
                    print(f"     涨幅: {row['涨跌幅']:.2f}% | 量比: {row['量比']:.2f} | "
                          f"换手率: {row['换手率']:.2f}% | 流通市值: {row['流通市值_亿']:.1f}亿")
                    print(f"     💰 主力净流入: {row['主力净流入']/1e8:.2f}亿 ({row['主力占比']:.2f}%)")
                    print(f"     💎 超大单净流入: {row['超大单净流入']/1e8:.2f}亿 ({row['超大单占比']:.2f}%)")
                    if '胜率' in row:
                        print(f"     📊 60日胜率: {row['胜率']} (上涨{row['上涨天数']}天 vs 下跌{row['下跌天数']}天)")
                    if row['主题得分'] > 0:
                        print(f"     🎯 {row['匹配主题']}")
            
            # 2. 显示主力资金流入股
            if not buy.empty:
                print(f"\n{'='*50}")
                print(f"⭐⭐ 【主力资金流入 - 看涨】({len(buy)}只)")
                print(f"{'='*50}")
                
                for idx, row in buy.iterrows():
                    print(f"\n  📈 {row['代码']} | {row['名称']}")
                    print(f"     涨幅: {row['涨跌幅']:.2f}% | 量比: {row['量比']:.2f} | "
                          f"换手率: {row['换手率']:.2f}% | 流通市值: {row['流通市值_亿']:.1f}亿")
                    print(f"     💰 主力净流入: {row['主力净流入']/1e8:.2f}亿 ({row['主力占比']:.2f}%)")
                    if '胜率' in row:
                        print(f"     📊 60日胜率: {row['胜率']} (上涨{row['上涨天数']}天 vs 下跌{row['下跌天数']}天)")
                    if row['主题得分'] > 0:
                        print(f"     🎯 {row['匹配主题']}")
            
            # 3. 显示中性资金流向股
            if not neutral.empty:
                print(f"\n{'='*50}")
                print(f"⭐ 【资金中性 - 技术面良好】({len(neutral)}只)")
                print(f"{'='*50}")
                
                for idx, row in neutral.iterrows():
                    print(f"\n  📌 {row['代码']} | {row['名称']}")
                    print(f"     涨幅: {row['涨跌幅']:.2f}% | 量比: {row['量比']:.2f} | "
                          f"换手率: {row['换手率']:.2f}% | 流通市值: {row['流通市值_亿']:.1f}亿")
                    print(f"     💰 主力净流入: {row['主力净流入']/1e8:.2f}亿 ({row['主力占比']:.2f}%)")
                    if '胜率' in row:
                        print(f"     📊 60日胜率: {row['胜率']} (上涨{row['上涨天数']}天 vs 下跌{row['下跌天数']}天)")
            
            # 输出股票代码列表
            print("\n" + "-" * 50)
            print("📋 股票代码汇总:")
            
            if not strong_buy.empty:
                print(f"   🔥 超大单强势: {', '.join(strong_buy['代码'].tolist())}")
            if not buy.empty:
                print(f"   📈 主力流入: {', '.join(buy['代码'].tolist())}")
            if not neutral.empty:
                print(f"   📌 资金中性: {', '.join(neutral['代码'].tolist())}")
            
            # 输出建议
            print("\n" + "-" * 50)
            print("💡 操作建议:")
            print("   【资金流向策略】")
            if not strong_buy.empty:
                print(f"   ⭐⭐⭐ 最优先: 超大单强势股，主力资金积极买入，后续上涨概率大")
                print(f"   → 重点关注: {', '.join(strong_buy['代码'].tolist()[:3])}")
            if not buy.empty:
                print(f"   ⭐⭐ 次优先: 主力资金流入股，有一定上涨动力")
            if not neutral.empty:
                print(f"   ⭐ 可选: 资金中性但技术面良好的股票，需谨慎观察")
            
            print("\n   【操作要点】")
            print("   1. 次日竞价阶段观察超大单和大单是否继续流入")
            print("   2. 若高开2%以上且资金继续流入，可考虑追涨")
            print("   3. 若资金转为流出，立即止损离场")
            print("   4. 严格遵守纪律：主力资金跑了，坚决不碰！")
            
            if self.current_month == 4:
                print("\n   ⚠️ 4月年报季警示: 注意规避业绩雷，建议轻仓观望!")
        
        print("\n" + "=" * 70)
        print("⚠️  风险提示: 本筛选仅供参考，不构成投资建议")
        print("    投资有风险，入市需谨慎")
        print("=" * 70)


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
    print("【A股次日冲高标的筛选系统 v5.0】")
    print("=" * 70)
    print("\n请选择操作:")
    print("  1. 全市场筛选（默认）")
    print("  2. 指定板块/概念筛选")
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
