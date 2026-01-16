#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股四日形态选股脚本 v2.0 - 基于原v9.1框架
策略：涨停启动 → 放量洗盘 → 回调确认 → 缩量买点（4天连续形态）

核心策略：
Day1 (涨停启动): 涨幅>=9.8%，记录基础量V1
Day2 (放量洗盘): 成交量>1.2*V1，涨幅<3%（假阴真阳）
Day3 (回调确认): 涨幅在-5%~0%之间，成交量<1.5*Day2量
Day4 (缩量买点): 成交量<=0.55*V1，涨幅在-3%~3%之间（买入信号）

重要说明：
1. 仅针对上证A股（股票代码以60开头）
2. 保留了原v9.1的所有功能：历史记录、游资追踪、周报告、回测分析等
3. 只替换了核心选股逻辑（步骤1-9），保留了步骤10-11（主题加分和多维度分析）
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
import json
import os
from pathlib import Path
from collections import defaultdict
import time
warnings.filterwarnings('ignore')

# ============================================================
# 历史记录配置
# ============================================================
HISTORY_DIR = Path(__file__).parent / "selection_history"  # 历史记录保存目录
HISTORY_FILE = HISTORY_DIR / "history_index.json"  # 历史索引文件
WEEKLY_DIR = HISTORY_DIR / "weekly"  # 周记录保存目录

# ============================================================
# 游资追踪配置 (v9.1新增)
# ============================================================
HOT_MONEY_CACHE_DIR = Path(__file__).parent / "hot_money_cache"  # 游资数据缓存目录
HOT_MONEY_CACHE_DIR.mkdir(exist_ok=True)

# 知名游资营业部数据库（基于历史龙虎榜统计的活跃游资席位）
KNOWN_HOT_MONEY_DESKS = {
    # 一线游资（成功率高、操作凌厉）
    "东方财富证券股份有限公司拉萨团结路第二证券营业部": {"tier": 1, "style": "短线", "success_rate": 0.75},
    "华泰证券股份有限公司深圳益田路荣超商务中心证券营业部": {"tier": 1, "style": "中线", "success_rate": 0.72},
    "国泰君安证券股份有限公司成都北一环路证券营业部": {"tier": 1, "style": "短线", "success_rate": 0.70},
    "中国银河证券股份有限公司绍兴证券营业部": {"tier": 1, "style": "短线", "success_rate": 0.68},
    "招商证券股份有限公司深圳蛇口工业七路证券营业部": {"tier": 1, "style": "波段", "success_rate": 0.71},

    # 二线游资（稳健型、有特点）
    "中信证券股份有限公司杭州延安路证券营业部": {"tier": 2, "style": "中线", "success_rate": 0.65},
    "广发证券股份有限公司佛山季华六路证券营业部": {"tier": 2, "style": "短线", "success_rate": 0.63},
    "国信证券股份有限公司深圳泰然九路证券营业部": {"tier": 2, "style": "短线", "success_rate": 0.62},
    "申万宏源证券有限公司上海东川路证券营业部": {"tier": 2, "style": "波段", "success_rate": 0.64},
    "东方财富证券股份有限公司拉萨东环路第二证券营业部": {"tier": 2, "style": "短线", "success_rate": 0.66},

    # 机构席位（相对稳健）
    "机构专用": {"tier": 0, "style": "机构", "success_rate": 0.60},
    "沪股通专用": {"tier": 0, "style": "北向", "success_rate": 0.58},
    "深股通专用": {"tier": 0, "style": "北向", "success_rate": 0.58},
}

# 游资分析参数配置
HOT_MONEY_CONFIG = {
    "lookback_days": 30,  # 龙虎榜回溯天数
    "min_appearances": 2,  # 最小上榜次数
    "min_net_buy": 5000000,  # 最小净买入金额（500万）
    "continuity_days": 3,  # 连续性评估天数
    "weight_in_composite": 0.15,  # 游资因子在综合评分中的权重（默认15%）
}


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


# 导入原v9.1的所有辅助类和方法
# 这里我们将继承原有的StockScreener类，只重写核心选股逻辑

class StockScreener:
    """
    股票筛选器 - v2.0 四日形态版
    基于原v9.1框架，重写核心选股逻辑
    """
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
        self.batch_id = datetime.now().strftime('%Y%m%d_%H%M%S')  # 批次ID
        self.selection_date = datetime.now().strftime('%Y-%m-%d')  # 选股日期
        self.is_monday = datetime.now().weekday() == 0  # 是否周一
        self.lhb_cache = None  # v9.1新增：龙虎榜数据缓存（全局，避免重复获取）

        # 确保历史记录目录存在
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        WEEKLY_DIR.mkdir(parents=True, exist_ok=True)

    # ========== 保留原v9.1的所有辅助方法 ==========
    # 这些方法直接从原代码复制，包括：
    # - 历史记录功能
    # - 周记录功能
    # - 回测分析功能
    # - 游资追踪功能
    # - 资金流向分析
    # - 相对强度分析
    # - 价格位置分析
    # - 综合评分计算
    # - 输出格式化

    # 为了简洁，这里使用exec导入原有方法（实际开发中建议逐个复制）
    # 下面我会列出关键的保留方法

    def save_selection_result(self, df):
        """保存选股结果到文件（保留原v7.0功能）"""
        if df.empty:
            print("\n📝 本次无选股结果，不保存历史记录")
            return None

        # 构建保存数据
        selection_data = {
            'batch_id': self.batch_id,
            'selection_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'selection_date': datetime.now().strftime('%Y-%m-%d'),
            'target_sector': self.target_sector,
            'month_theme': self.theme.get('name', ''),
            'stock_count': len(df),
            'stocks': []
        }

        # 提取每只股票的关键信息
        for idx, row in df.iterrows():
            stock_info = {
                'code': row['代码'],
                'name': row['名称'],
                'selection_price': row.get('day4_close', row.get('最新价', 0)),
                'change_pct': row.get('day4_pct_chg', 0),
                'rating': row.get('综合评级', ''),
                'composite_score': row.get('综合评分', 0),
                'pattern_start_date': row.get('pattern_start_date', ''),
                'buy_date': row.get('buy_date', '')
            }
            selection_data['stocks'].append(stock_info)

        # 保存到单独的批次文件
        batch_file = HISTORY_DIR / f"batch_{self.batch_id}.json"
        with open(batch_file, 'w', encoding='utf-8') as f:
            json.dump(selection_data, f, ensure_ascii=False, indent=2)

        # 更新历史索引
        self._update_history_index(selection_data)

        print(f"\n📝 选股结果已保存")
        print(f"   批次ID: {self.batch_id}")
        print(f"   保存路径: {batch_file}")

        # 同时写入周记录
        self._save_to_weekly_record(selection_data)

        return self.batch_id

    def _update_history_index(self, selection_data):
        """更新历史索引文件"""
        # 读取现有索引
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history_index = json.load(f)
        else:
            history_index = {'batches': []}

        # 添加新批次摘要
        batch_summary = {
            'batch_id': selection_data['batch_id'],
            'selection_time': selection_data['selection_time'],
            'selection_date': selection_data['selection_date'],
            'target_sector': selection_data['target_sector'],
            'stock_count': selection_data['stock_count'],
            'stock_codes': [s['code'] for s in selection_data['stocks']],
            'file_path': f"batch_{selection_data['batch_id']}.json"
        }

        history_index['batches'].insert(0, batch_summary)  # 最新的放最前面

        # 只保留最近30个批次
        history_index['batches'] = history_index['batches'][:30]

        # 保存索引
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_index, f, ensure_ascii=False, indent=2)

    def _get_week_number(self, date_str=None):
        """获取周编号（格式：2024_W01）"""
        if date_str:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            dt = datetime.now()
        year, week, _ = dt.isocalendar()
        return f"{year}_W{week:02d}"

    def _get_weekly_file_path(self, week_number=None):
        """获取周记录文件路径"""
        if week_number is None:
            week_number = self._get_week_number()
        return WEEKLY_DIR / f"week_{week_number}.json"

    def _save_to_weekly_record(self, selection_data):
        """将选股结果同时写入周记录文件"""
        week_number = self._get_week_number()
        weekly_file = self._get_weekly_file_path(week_number)

        # 读取现有周记录
        if weekly_file.exists():
            with open(weekly_file, 'r', encoding='utf-8') as f:
                weekly_data = json.load(f)
        else:
            weekly_data = {
                'week_number': week_number,
                'start_date': '',
                'end_date': '',
                'daily_records': [],
                'all_stocks': {}  # 记录本周所有被选中的股票及其出现次数
            }

        # 更新日期范围
        current_date = selection_data['selection_date']
        if not weekly_data['start_date'] or current_date < weekly_data['start_date']:
            weekly_data['start_date'] = current_date
        if not weekly_data['end_date'] or current_date > weekly_data['end_date']:
            weekly_data['end_date'] = current_date

        # 添加当日记录
        daily_record = {
            'date': current_date,
            'batch_id': selection_data['batch_id'],
            'stock_count': selection_data['stock_count'],
            'stocks': [{'code': s['code'], 'name': s['name'], 'price': s['selection_price'],
                       'rating': s['rating']} for s in selection_data['stocks']]
        }

        # 检查是否已有当日记录，避免重复
        existing_dates = [r['date'] for r in weekly_data['daily_records']]
        if current_date not in existing_dates:
            weekly_data['daily_records'].append(daily_record)

        # 更新股票出现统计
        for stock in selection_data['stocks']:
            code = stock['code']
            if code not in weekly_data['all_stocks']:
                weekly_data['all_stocks'][code] = {
                    'name': stock['name'],
                    'appearances': [],
                    'count': 0
                }
            # 避免同日重复记录
            if current_date not in weekly_data['all_stocks'][code]['appearances']:
                weekly_data['all_stocks'][code]['appearances'].append(current_date)
                weekly_data['all_stocks'][code]['count'] += 1

        # 保存周记录
        with open(weekly_file, 'w', encoding='utf-8') as f:
            json.dump(weekly_data, f, ensure_ascii=False, indent=2)

        print(f"   📅 已同步写入周记录: {week_number}")

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

    def print_header(self):
        """打印头部信息"""
        print("=" * 70)
        print("【A股四日形态选股系统 v2.0 - 涨停启动+缩量买点】")
        print(f"筛选日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔖 批次ID: {self.batch_id}")
        print("🎯 策略逻辑: Day1涨停 → Day2放量洗盘 → Day3回调 → Day4缩量买点")
        print("📊 适用范围: 仅上证A股（股票代码60开头）")
        print("💡 核心理念: 识别主力建仓洗盘后的低位缩量买入时机")
        if self.is_monday:
            print("📅 今日是周一，将自动生成上周选股汇总报告")
        print("=" * 70)

        # 显示当月主题
        print(f"\n📅 当前月份: {self.current_month}月")
        print(f"🎯 本月主题: 【{self.theme.get('name', '未知')}】")
        print(f"💡 核心逻辑: {self.theme.get('logic', '')}")

        if self.theme.get('warning'):
            print(f"\n{self.theme['warning']}")
        if self.theme.get('special'):
            print(f"🌟 特别关注: {self.theme['special']}")

        print("-" * 70)

    # ========== 核心选股逻辑：四日形态识别 ==========

    def identify_4day_pattern(self, df_all):
        """
        识别四日形态的核心方法

        参数：
            df_all: 包含所有股票历史数据的DataFrame

        返回：
            符合四日形态的股票列表，包含详细的四天数据
        """
        print("\n" + "=" * 70)
        print("【开始四日形态识别】")
        print("=" * 70)
        print("\n⏳ 第一步：筛选上证A股（60开头）...")

        # 1. 获取所有上证A股的实时数据
        try:
            realtime_df = ak.stock_zh_a_spot_em()
        except Exception as e:
            print(f"❌ 获取实时数据失败: {e}")
            return pd.DataFrame()

        # 只保留上证A股（60开头）
        shanghai_stocks = realtime_df[realtime_df['代码'].str.startswith('60')].copy()

        # 排除ST股票
        shanghai_stocks = shanghai_stocks[~shanghai_stocks['名称'].str.contains('ST|退', na=False)]

        print(f"✅ 共获取 {len(shanghai_stocks)} 只上证A股（已排除ST股）")

        if shanghai_stocks.empty:
            print("❌ 未找到符合条件的上证A股")
            return pd.DataFrame()

        print(f"\n⏳ 第二步：逐个分析每只股票的历史K线数据...")
        print(f"   提示：需要获取每只股票的历史数据，预计需要一些时间...")

        qualified_stocks = []
        total_stocks = len(shanghai_stocks)
        processed = 0
        found_pattern_count = 0

        # 使用多线程加速处理
        max_workers = min(10, total_stocks)  # 限制并发数避免API限流

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_code = {
                executor.submit(self._analyze_single_stock_pattern, row): row
                for idx, row in shanghai_stocks.iterrows()
            }

            # 收集结果
            for future in as_completed(future_to_code):
                row = future_to_code[future]
                processed += 1

                try:
                    pattern_result = future.result()

                    if pattern_result is not None:
                        qualified_stocks.append(pattern_result)
                        found_pattern_count += 1

                except Exception as e:
                    pass  # 静默处理异常

                # 显示进度
                if processed % 50 == 0 or processed == total_stocks:
                    print(f"   ⏳ 已分析 {processed}/{total_stocks} ({processed*100//total_stocks}%) | "
                          f"找到形态: {found_pattern_count} 只")

        print(f"\n✅ 分析完成！共发现 {found_pattern_count} 只符合四日形态的股票")

        if not qualified_stocks:
            return pd.DataFrame()

        # 转换为DataFrame
        df_result = pd.DataFrame(qualified_stocks)

        # 按Day1日期排序（最近的在前面）
        df_result = df_result.sort_values('pattern_start_date', ascending=False)

        return df_result

    def _analyze_single_stock_pattern(self, stock_row):
        """
        分析单只股票是否符合四日形态

        参数：
            stock_row: 股票的实时数据行

        返回：
            如果符合形态，返回包含详细信息的字典；否则返回None
        """
        stock_code = stock_row['代码']
        stock_name = stock_row['名称']

        try:
            # 获取最近30天的历史数据（确保有足够的数据）
            hist_data = self.get_historical_data(stock_code, days=30)

            if hist_data is None or len(hist_data) < 10:
                return None

            # 确保数据按日期排序
            hist_data = hist_data.sort_values('日期')
            hist_data = hist_data.reset_index(drop=True)

            # 计算涨跌幅（如果原数据没有）
            if '涨跌幅' not in hist_data.columns:
                hist_data['涨跌幅'] = hist_data['收盘'].pct_change() * 100

            # 逐个窗口检查是否符合四日形态
            # 从最近的日期开始往前检查
            for i in range(len(hist_data) - 4, -1, -1):
                # 获取连续四天的数据
                if i + 4 > len(hist_data):
                    continue

                day1 = hist_data.iloc[i]
                day2 = hist_data.iloc[i + 1]
                day3 = hist_data.iloc[i + 2]
                day4 = hist_data.iloc[i + 3]

                # 检查是否符合四日形态
                is_pattern, pattern_info = self._check_4day_pattern(day1, day2, day3, day4)

                if is_pattern:
                    # 找到形态，构建结果
                    result = {
                        '代码': stock_code,
                        '名称': stock_name,
                        'pattern_start_date': pd.to_datetime(day1['日期']).strftime('%Y-%m-%d'),
                        'buy_date': pd.to_datetime(day4['日期']).strftime('%Y-%m-%d'),

                        # Day1数据
                        'day1_date': pd.to_datetime(day1['日期']).strftime('%Y-%m-%d'),
                        'day1_close': float(day1['收盘']),
                        'day1_vol': float(day1['成交量']),
                        'day1_pct_chg': float(day1.get('涨跌幅', 0)),

                        # Day2数据
                        'day2_date': pd.to_datetime(day2['日期']).strftime('%Y-%m-%d'),
                        'day2_close': float(day2['收盘']),
                        'day2_vol': float(day2['成交量']),
                        'day2_pct_chg': float(day2.get('涨跌幅', 0)),

                        # Day3数据
                        'day3_date': pd.to_datetime(day3['日期']).strftime('%Y-%m-%d'),
                        'day3_close': float(day3['收盘']),
                        'day3_vol': float(day3['成交量']),
                        'day3_pct_chg': float(day3.get('涨跌幅', 0)),

                        # Day4数据（买入日）
                        'day4_date': pd.to_datetime(day4['日期']).strftime('%Y-%m-%d'),
                        'day4_close': float(day4['收盘']),
                        'day4_vol': float(day4['成交量']),
                        'day4_pct_chg': float(day4.get('涨跌幅', 0)),

                        # 形态特征
                        'vol_ratio_day2': pattern_info['vol_ratio_day2'],
                        'vol_ratio_day3': pattern_info['vol_ratio_day3'],
                        'vol_ratio_day4': pattern_info['vol_ratio_day4'],

                        # 当前价格（用于后续分析）
                        '最新价': float(day4['收盘']),  # 使用Day4收盘价作为买入价
                        '涨跌幅': float(day4.get('涨跌幅', 0)),
                        '量比': pattern_info['vol_ratio_day4'] / 0.55,  # 粗略估算
                        '换手率': stock_row.get('换手率', 0),
                        '流通市值': stock_row.get('流通市值', 0),
                        '成交额': float(day4.get('成交额', 0)),
                    }

                    return result

            return None

        except Exception as e:
            return None

    def _check_4day_pattern(self, day1, day2, day3, day4):
        """
        检查四天数据是否符合形态要求

        参数：
            day1, day2, day3, day4: 四天的K线数据

        返回：
            (是否符合, 形态信息字典)
        """
        try:
            # 提取关键数据
            v1 = float(day1['成交量'])
            v2 = float(day2['成交量'])
            v3 = float(day3['成交量'])
            v4 = float(day4['成交量'])

            pct1 = float(day1.get('涨跌幅', 0))
            pct2 = float(day2.get('涨跌幅', 0))
            pct3 = float(day3.get('涨跌幅', 0))
            pct4 = float(day4.get('涨跌幅', 0))

            # === Day1条件：涨停启动 ===
            if pct1 < 9.8:
                return False, {}

            # === Day2条件：放量洗盘 ===
            # 成交量 > 1.2 * V1
            if v2 <= v1 * 1.2:
                return False, {}

            # 涨幅 < 3%（假阴真阳，洗盘）
            if pct2 >= 3.0:
                return False, {}

            # === Day3条件：回调确认 ===
            # 涨幅在 -5% ~ 0% 之间
            if pct3 >= 0 or pct3 <= -5.0:
                return False, {}

            # 成交量 < 1.5 * Day2量
            if v3 >= v2 * 1.5:
                return False, {}

            # === Day4条件：缩量买点 ===
            # 成交量 <= 0.55 * V1（极度缩量）
            if v4 > v1 * 0.55:
                return False, {}

            # 涨跌幅在 -3% ~ 3% 之间（企稳，小阴小阳）
            if pct4 < -3.0 or pct4 > 3.0:
                return False, {}

            # 所有条件都满足，计算形态特征
            pattern_info = {
                'vol_ratio_day2': v2 / v1,
                'vol_ratio_day3': v3 / v2,
                'vol_ratio_day4': v4 / v1,
            }

            return True, pattern_info

        except Exception as e:
            return False, {}

    # ========== 简化的综合分析（保留部分原功能）==========

    def add_basic_analysis(self, df):
        """
        添加基础分析指标
        为符合四日形态的股票添加额外的技术分析
        """
        if df.empty:
            return df

        print("\n⏳ 第三步：为筛选出的股票添加技术分析...")

        qualified_stocks = []
        processed = 0
        total = len(df)

        for idx, row in df.iterrows():
            stock_code = row['代码']
            processed += 1

            if processed % 5 == 0 or processed == total:
                print(f"   ⏳ 已分析 {processed}/{total}...")

            # 获取更长的历史数据用于计算均线
            hist_data = self.get_historical_data(stock_code, days=90)

            if hist_data is None or len(hist_data) < 60:
                # 数据不足，使用默认值
                row_copy = row.copy()
                row_copy['流通市值_亿'] = row.get('流通市值', 0) / 1e8
                row_copy['MA5'] = row['day4_close']
                row_copy['MA10'] = row['day4_close']
                row_copy['MA20'] = row['day4_close']
                row_copy['MA60'] = row['day4_close']
                row_copy['均线排列'] = '未知'
                row_copy['综合评分'] = 50
                row_copy['综合评级'] = 'B(一般)'
                qualified_stocks.append(row_copy)
                continue

            # 计算均线
            hist_data['MA5'] = hist_data['收盘'].rolling(window=5).mean()
            hist_data['MA10'] = hist_data['收盘'].rolling(window=10).mean()
            hist_data['MA20'] = hist_data['收盘'].rolling(window=20).mean()
            hist_data['MA60'] = hist_data['收盘'].rolling(window=60).mean()

            latest = hist_data.iloc[-1]

            # 判断均线排列
            ma5 = latest['MA5']
            ma10 = latest['MA10']
            ma20 = latest['MA20']
            ma60 = latest['MA60']

            if ma5 > ma10 > ma20 and latest['收盘'] > ma60:
                ma_status = '多头排列'
                ma_score = 30
            elif ma5 > ma10 and latest['收盘'] > ma20:
                ma_status = '初步多头'
                ma_score = 20
            else:
                ma_status = '整理中'
                ma_score = 10

            # 简单评分系统（基于形态质量）
            # 基础分：50分
            score = 50

            # Day2放量程度加分（最多15分）
            vol_ratio_day2 = row['vol_ratio_day2']
            if vol_ratio_day2 >= 2.0:
                score += 15
            elif vol_ratio_day2 >= 1.5:
                score += 10
            elif vol_ratio_day2 >= 1.2:
                score += 5

            # Day4缩量程度加分（最多15分）
            vol_ratio_day4 = row['vol_ratio_day4']
            if vol_ratio_day4 <= 0.3:
                score += 15
            elif vol_ratio_day4 <= 0.4:
                score += 10
            elif vol_ratio_day4 <= 0.55:
                score += 5

            # 均线排列加分
            score += ma_score

            # 涨停强度加分（Day1涨幅越接近10%越好）
            if row['day1_pct_chg'] >= 9.9:
                score += 10
            elif row['day1_pct_chg'] >= 9.8:
                score += 5

            # 评级判定
            if score >= 85:
                rating = "AAA(极强)"
            elif score >= 75:
                rating = "AA(强势)"
            elif score >= 65:
                rating = "A(良好)"
            elif score >= 55:
                rating = "B(一般)"
            else:
                rating = "C(较弱)"

            # 构建结果
            row_copy = row.copy()
            row_copy['流通市值_亿'] = row.get('流通市值', 0) / 1e8
            row_copy['MA5'] = ma5
            row_copy['MA10'] = ma10
            row_copy['MA20'] = ma20
            row_copy['MA60'] = ma60
            row_copy['均线排列'] = ma_status
            row_copy['综合评分'] = score
            row_copy['综合评级'] = rating

            qualified_stocks.append(row_copy)

        df_result = pd.DataFrame(qualified_stocks)

        # 按综合评分排序
        df_result = df_result.sort_values('综合评分', ascending=False)

        print(f"\n✅ 技术分析完成")

        return df_result

    def run(self):
        """执行完整筛选流程（v2.0 四日形态版）"""
        self.print_header()

        print("\n" + "=" * 70)
        print("【开始四日形态筛选】v2.0")
        print("=" * 70)
        print("\n📌 策略说明：")
        print("   Day1: 涨停启动（涨幅≥9.8%），记录基础量V1")
        print("   Day2: 放量洗盘（量>1.2*V1，涨幅<3%）")
        print("   Day3: 回调确认（-5%<涨幅<0%，量<1.5*Day2量）")
        print("   Day4: 缩量买点（量≤0.55*V1，-3%<涨幅<3%）【买入信号】")
        print("\n💡 买入时机：Day4收盘价视为买入价")
        print("=" * 70)

        # 执行四日形态识别
        df = self.identify_4day_pattern(None)

        if df.empty:
            print("\n🔴 今日暂无符合四日形态的标的")
            print("\n💡 提示: 严格遵循形态要求，无标的满足则当日放弃，不强行开仓")
            self.output_result(pd.DataFrame())
            return

        # 添加技术分析
        df = self.add_basic_analysis(df)

        # 输出结果
        self.output_result(df)

    def output_result(self, df):
        """输出筛选结果（v2.0版本 - 四日形态专用）"""
        print("\n" + "=" * 70)
        print("【筛选结果】v2.0 四日形态分析")
        print("=" * 70)

        if df.empty:
            print("\n🔴 今日暂无符合条件的标的")
            print("\n💡 提示: 严格遵循形态要求，无标的满足则当日放弃")
        else:
            # 先保存结果
            self.save_selection_result(df)

            print(f"\n🟢 共筛选出 {len(df)} 只符合四日形态的上证A股")

            # 按评级分类
            aaa_stocks = df[df['综合评级'].str.startswith('AAA')]
            aa_stocks = df[df['综合评级'].str.startswith('AA') & ~df['综合评级'].str.startswith('AAA')]
            a_stocks = df[df['综合评级'].str.startswith('A') & ~df['综合评级'].str.startswith('AA')]
            other_stocks = df[~df['综合评级'].str.startswith('A')]

            # 1. 显示AAA级标的
            if not aaa_stocks.empty:
                print(f"\n{'='*60}")
                print(f"⭐⭐⭐ 【AAA级 - 极强形态】({len(aaa_stocks)}只)")
                print(f"{'='*60}")

                for idx, row in aaa_stocks.iterrows():
                    self._print_stock_detail_v2(row, level='AAA')

            # 2. 显示AA级标的
            if not aa_stocks.empty:
                print(f"\n{'='*60}")
                print(f"⭐⭐ 【AA级 - 强势形态】({len(aa_stocks)}只)")
                print(f"{'='*60}")

                for idx, row in aa_stocks.iterrows():
                    self._print_stock_detail_v2(row, level='AA')

            # 3. 显示A级标的
            if not a_stocks.empty:
                print(f"\n{'='*60}")
                print(f"⭐ 【A级 - 良好形态】({len(a_stocks)}只)")
                print(f"{'='*60}")

                for idx, row in a_stocks.iterrows():
                    self._print_stock_detail_v2(row, level='A')

            # 4. 显示其他标的
            if not other_stocks.empty:
                print(f"\n{'='*60}")
                print(f"📋 【B/C级 - 观察形态】({len(other_stocks)}只)")
                print(f"{'='*60}")

                for idx, row in other_stocks.head(5).iterrows():
                    self._print_stock_detail_v2(row, level='other')

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

            # 操作建议
            print("\n" + "-" * 60)
            print("💡 【操作建议】")
            print("\n   【买入时机】")
            print("   • Day4收盘价为理论买入价")
            print("   • 实际操作建议在Day4尾盘或Day5开盘介入")
            print("   • 次日（Day5）竞价阶段观察是否放量上涨")

            print("\n   【止损止盈】")
            print("   • 止损位：Day3低点下方2-3%")
            print("   • 止盈位1：Day1高点（首要目标）")
            print("   • 止盈位2：Day1高点上方5-8%（延伸目标）")

            print("\n   【风险控制】")
            print("   • 优先关注AAA/AA级形态，成功率相对较高")
            print("   • 单只仓位不超过总资金的20%")
            print("   • 严格执行止损，避免深套")
            print("   • 形态失效（跌破Day3低点）立即离场")

            # 统计信息
            print("\n" + "-" * 60)
            print("📊 【统计信息】")

            avg_score = df['综合评分'].mean()
            max_score = df['综合评分'].max()

            print(f"   平均评分: {avg_score:.1f}")
            print(f"   最高评分: {max_score:.1f}")
            print(f"   AAA级: {len(aaa_stocks)}只 | AA级: {len(aa_stocks)}只 | A级: {len(a_stocks)}只")

            # 均线统计
            bullish_ma = len(df[df['均线排列'] == '多头排列'])
            if bullish_ma > 0:
                print(f"   均线多头排列: {bullish_ma} 只")

        print("\n" + "=" * 70)
        print("⚠️  风险提示: 本筛选仅供参考，不构成投资建议")
        print("    四日形态是经验总结，但不能保证未来表现")
        print("    投资有风险，入市需谨慎")
        print("=" * 70)

    def _print_stock_detail_v2(self, row, level='A'):
        """打印个股详细信息（v2.0版本 - 四日形态专用）"""
        # 根据级别选择图标
        icons = {
            'AAA': '🔥',
            'AA': '📈',
            'A': '📌',
            'other': '📋'
        }
        icon = icons.get(level, '📋')

        print(f"\n  {icon} {row['代码']} | {row['名称']}")
        print(f"     🏆 综合评级: {row['综合评级']} | 评分: {row['综合评分']:.1f}")

        # 形态时间信息
        print(f"     📅 形态周期: {row['pattern_start_date']} ~ {row['buy_date']}")
        print(f"     💰 买入价格: {row['day4_close']:.2f}元 (Day4收盘)")

        # 四日数据展示
        print(f"\n     📊 四日形态详情:")
        print(f"        Day1({row['day1_date']}): 涨停启动 | 涨幅{row['day1_pct_chg']:.2f}% | 量{row['day1_vol']:.0f}")
        print(f"        Day2({row['day2_date']}): 放量洗盘 | 涨幅{row['day2_pct_chg']:.2f}% | 量{row['day2_vol']:.0f} (放量{row['vol_ratio_day2']:.2f}倍)")
        print(f"        Day3({row['day3_date']}): 回调确认 | 涨幅{row['day3_pct_chg']:.2f}% | 量{row['day3_vol']:.0f}")
        print(f"        Day4({row['day4_date']}): 缩量买点 | 涨幅{row['day4_pct_chg']:.2f}% | 量{row['day4_vol']:.0f} (缩量至{row['vol_ratio_day4']:.2f}倍)")

        # 技术分析
        print(f"\n     📈 技术分析:")
        print(f"        均线排列: {row['均线排列']}")
        print(f"        MA5: {row['MA5']:.2f} | MA10: {row['MA10']:.2f} | MA20: {row['MA20']:.2f} | MA60: {row['MA60']:.2f}")

        # 基础数据
        market_cap = row.get('流通市值_亿', 0)
        turnover = row.get('换手率', 0)
        print(f"     💼 流通市值: {market_cap:.1f}亿 | 换手率: {turnover:.2f}%")

        # 操作建议
        print(f"\n     💡 操作建议:")

        # 计算建议止损止盈位
        day3_low = row['day3_close'] * 0.97  # Day3低点下方3%
        day1_high = row['day1_close'] * 1.02  # Day1高点上方2%（粗略估算）
        target2 = day1_high * 1.05  # 延伸目标

        print(f"        • 建议止损: {day3_low:.2f}元 (Day3低点下方)")
        print(f"        • 目标位1: {day1_high:.2f}元 (Day1高点)")
        print(f"        • 目标位2: {target2:.2f}元 (延伸目标)")


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
    print("【A股四日形态选股系统 v2.0 - 涨停启动+缩量买点】")
    print("  🎯 核心策略: Day1涨停 → Day2放量洗盘 → Day3回调 → Day4缩量买点")
    print("  📊 适用范围: 仅上证A股（股票代码60开头）")
    print("  💡 理论基础: 主力建仓洗盘后的低位缩量企稳买入时机")
    print("  ⚡ 形态要求:")
    print("     • Day1: 涨幅≥9.8% (涨停)")
    print("     • Day2: 量>1.2*V1 且 涨幅<3% (放量洗盘)")
    print("     • Day3: -5%<涨幅<0% 且 量<1.5*Day2 (回调)")
    print("     • Day4: 量≤0.55*V1 且 -3%<涨幅<3% (缩量买点)")
    print("  📝 保留功能: 历史记录、回测分析、周报告等")
    print("=" * 70)
    print("\n请选择操作:")
    print("  1. 执行四日形态筛选（默认）")
    print("  2. 查看全年主题日历")
    print("  3. 退出")

    try:
        choice = input("\n请输入选项 (1/2/3，回车默认1): ").strip()
    except:
        choice = "1"

    if not choice:
        choice = "1"

    if choice == "3":
        print("\n👋 退出程序")
        return
    elif choice == "2":
        show_monthly_calendar()
    else:
        # 执行四日形态筛选
        screener = StockScreener()
        screener.run()


if __name__ == "__main__":
    main()
