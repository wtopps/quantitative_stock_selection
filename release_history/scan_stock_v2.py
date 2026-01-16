#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股次日冲高标的筛选脚本 v2.0
基于量化条件 + 月份主题 + 形态分析
锁定当日强势、筹码健康、契合季节性热点的个股
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
    def __init__(self):
        self.today = datetime.now().strftime('%Y%m%d')
        self.current_month = datetime.now().month
        self.theme = MONTHLY_THEMES.get(self.current_month, {})
        self.results = []
        self.concept_stocks = {}  # 缓存概念板块数据
        
    def print_header(self):
        """打印头部信息"""
        print("=" * 70)
        print("【A股次日冲高标的筛选系统 v2.0】")
        print(f"筛选日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
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
        
    def get_realtime_data(self):
        """获取A股实时行情数据"""
        try:
            df = ak.stock_zh_a_spot_em()
            print(f"\n📊 获取到 {len(df)} 只股票的实时数据")
            return df
        except Exception as e:
            print(f"❌ 获取实时数据失败: {e}")
            return None
    
    def get_stock_industry(self):
        """获取股票行业分类"""
        try:
            df = ak.stock_board_industry_name_em()
            return df
        except:
            return None
    
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
    
    def check_theme_match(self, stock_code, stock_name):
        """检查股票是否匹配当月主题"""
        keywords = self.theme.get('keywords', [])
        
        # 1. 检查股票名称是否包含关键词
        for keyword in keywords:
            if keyword in stock_name:
                return True, keyword
        
        return False, None
    
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
    
    def step5_filter_by_volume_pattern(self, df):
        """第五步：成交量形态筛选 (台阶式稳步放大)"""
        print("\n" + "-" * 50)
        print("【第五步】动能确认: 成交量台阶式放大")
        
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
    
    def step6_filter_by_ma_trend(self, df):
        """第六步：趋势确认 (均线多头排列)"""
        print("\n" + "-" * 50)
        print("【第六步】趋势确认: 均线多头排列 (MA5>MA10>MA20, 股价>MA60)")
        
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
    
    def step7_filter_by_intraday_strength(self, df):
        """第七步：强度确认 (分时图强度)"""
        print("\n" + "-" * 50)
        print("【第七步】强度确认: 分时走势强于大盘")
        
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
    
    def step8_filter_by_win_rate(self, df):
        """第八步：胜率筛选 (近60个交易日上涨天数>下跌天数)"""
        print("\n" + "-" * 50)
        print("【第八步】胜率筛选: 近60个交易日上涨天数 > 下跌天数")
        
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
    
    def step9_theme_scoring(self, df):
        """第九步：月份主题加分"""
        print("\n" + "-" * 50)
        print(f"【第九步】主题加分: 匹配{self.current_month}月【{self.theme.get('name', '')}】主题")
        
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
        
        # 按主题得分排序
        df = df.sort_values(['主题得分', '涨跌幅'], ascending=[False, False])
        
        theme_matched = len(df[df['主题得分'] > 0])
        print(f"   ✅ 其中 {theme_matched} 只匹配当月主题")
        
        return df
    
    def run(self):
        """执行完整筛选流程"""
        self.print_header()
        
        # 获取实时数据
        df = self.get_realtime_data()
        if df is None or df.empty:
            print("\n❌ 无法获取数据，程序退出")
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
        
        print(f"\n⏳ 正在分析 {len(df)} 只股票的历史数据，请稍候...")
        
        # 第五步：成交量形态筛选
        df = self.step5_filter_by_volume_pattern(df)
        if df.empty:
            self.output_result(pd.DataFrame())
            return
        
        # 第六步：均线趋势筛选
        df = self.step6_filter_by_ma_trend(df)
        if df.empty:
            self.output_result(pd.DataFrame())
            return
        
        # 第七步：分时强度筛选
        df = self.step7_filter_by_intraday_strength(df)
        if df.empty:
            self.output_result(pd.DataFrame())
            return
        
        # 第八步：胜率筛选
        df = self.step8_filter_by_win_rate(df)
        if df.empty:
            self.output_result(pd.DataFrame())
            return
        
        # 第九步：月份主题加分
        df = self.step9_theme_scoring(df)
        
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
            # 分类显示：主题匹配 vs 非主题匹配
            theme_matched = df[df['主题得分'] > 0]
            non_matched = df[df['主题得分'] == 0]
            
            print(f"\n🟢 共筛选出 {len(df)} 只潜在次日冲高标的")
            
            if not theme_matched.empty:
                print(f"\n{'='*50}")
                print(f"🎯 【契合{self.current_month}月主题】- {self.theme.get('name', '')} ({len(theme_matched)}只)")
                print(f"{'='*50}")
                
                for idx, row in theme_matched.iterrows():
                    print(f"\n  🌟 {row['代码']} | {row['名称']}")
                    print(f"     涨幅: {row['涨跌幅']:.2f}% | 量比: {row['量比']:.2f} | "
                          f"换手率: {row['换手率']:.2f}% | 流通市值: {row['流通市值_亿']:.1f}亿")
                    if '胜率' in row:
                        print(f"     📊 60日胜率: {row['胜率']} (上涨{row['上涨天数']}天 vs 下跌{row['下跌天数']}天)")
                    print(f"     📌 匹配主题: {row['匹配主题']}")
            
            if not non_matched.empty:
                print(f"\n{'='*50}")
                print(f"📋 【其他符合条件标的】({len(non_matched)}只)")
                print(f"{'='*50}")
                
                for idx, row in non_matched.iterrows():
                    print(f"\n  📌 {row['代码']} | {row['名称']}")
                    print(f"     涨幅: {row['涨跌幅']:.2f}% | 量比: {row['量比']:.2f} | "
                          f"换手率: {row['换手率']:.2f}% | 流通市值: {row['流通市值_亿']:.1f}亿")
                    if '胜率' in row:
                        print(f"     📊 60日胜率: {row['胜率']} (上涨{row['上涨天数']}天 vs 下跌{row['下跌天数']}天)")
            
            # 输出股票代码列表
            print("\n" + "-" * 50)
            print("📋 股票代码汇总:")
            
            if not theme_matched.empty:
                print(f"   🎯 主题匹配: {', '.join(theme_matched['代码'].tolist())}")
            if not non_matched.empty:
                print(f"   📌 其他标的: {', '.join(non_matched['代码'].tolist())}")
            
            # 输出建议
            print("\n" + "-" * 50)
            print("💡 操作建议:")
            if not theme_matched.empty:
                print(f"   1. 优先关注主题匹配标的，契合{self.current_month}月【{self.theme.get('name', '')}】行情")
                print("   2. 次日竞价阶段观察资金承接情况")
                print("   3. 若高开2%以上可考虑追涨，否则等待回踩支撑")
            else:
                print("   1. 当前无主题匹配标的，谨慎操作")
                print("   2. 可小仓位参与技术形态良好的个股")
            
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
    print("\n请选择操作:")
    print("  1. 执行今日筛选")
    print("  2. 查看全年主题日历")
    print("  3. 直接筛选 (默认)")
    
    try:
        choice = input("\n请输入选项 (1/2/3，回车默认3): ").strip()
    except:
        choice = "3"
    
    if choice == "2":
        show_monthly_calendar()
    else:
        screener = StockScreener()
        screener.run()


if __name__ == "__main__":
    main()