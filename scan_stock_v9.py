#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股次日冲高标的筛选脚本 v9.1 - 游资追踪版
基于量化条件 + 月份主题 + 形态分析 + 主力资金流向 + 三维度综合评估 + 游资动向追踪

核心升级（v9.1 - 游资追踪版）：
1. 龙虎榜数据分析：获取个股上榜记录、营业部买卖明细
2. 游资强度评分：多维度计算游资介入强度（0-100分）
3. 买入时机判断：识别游资建仓、加仓、拉升、出货阶段
4. 持续性评估：评估游资操作的连续性和稳定性
5. 风险预警机制：识别游资撤退信号，设置风险预警
6. 因子加权整合：游资因子与现有因子加权组合（可调节）
7. 回测验证框架：验证加入游资因子后的策略表现提升
8. 优先排序输出：游资活跃且符合其他条件的股票优先展示

核心升级（v8.1 - 精准剪枝版）：
1. 收紧筛选条件：涨幅(-1%~5.5%)、量比(≥1.2)、换手率(10%~18%)、市值(40~120亿)
2. 板块限制：仅沪深主板，排除创业板（3开头）、科创板（688开头）、北交所
3. 综合评分阈值：只保留综合评分≥55的股票
4. 风险收益比筛选：只保留风险收益比≥1.5的股票
5. 数量限制：最多输出综合评分最高的前20只
6. 板块信息显示：在选股结果中显示每只股票的所属板块
7. 历史记录二级菜单：查看历史记录时可选择具体批次查看详情

核心升级（v8.0 - 短线优化版）：
1. 市场情绪指标：涨停家数、连板数、两市成交额，情绪过滤
2. 板块龙头识别：识别板块内涨幅、成交额领先的龙头股
3. 短周期胜率：从60日改为10日/20日，更贴近短线动能
4. 参数优化：涨幅区间(-2%~7%)、换手率(8%~20%)、市值(30~150亿)
5. 权重调整：资金流向权重提升至45%，强化资金驱动
6. 风险收益比：增加止损止盈位计算，风险收益比筛选
7. 月涨幅分层：允许月涨幅20-50%但近期回调的强势股

v7.1功能：
1. 周记录功能：每日选股结果自动写入周记录文件
2. 周一汇总报告：周一执行时自动生成上周选股与当前股价对比的汇总报告
3. 连续选中标识：连续2天以上被选中的股票会被重点标识，单独列出
4. 当前股价显示：选股结果中显示股票当前价格

v7.0功能：
1. 历史记录功能：每次选股结果自动保存到文件，带批次标识
2. 策略回测功能：执行时自动对比上次选出股票的实际涨幅表现

v6.0功能：
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
        self.batch_id = datetime.now().strftime('%Y%m%d_%H%M%S')  # 批次ID
        self.selection_date = datetime.now().strftime('%Y-%m-%d')  # 选股日期
        self.is_monday = datetime.now().weekday() == 0  # 是否周一
        self.lhb_cache = None  # v9.1新增：龙虎榜数据缓存（全局，避免重复获取）

        # 确保历史记录目录存在
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        WEEKLY_DIR.mkdir(parents=True, exist_ok=True)

    def save_selection_result(self, df):
        """
        保存选股结果到文件（v7.0新增）

        保存内容：
        - 批次ID（日期时间戳）
        - 选股时间
        - 目标板块（如有）
        - 选出的股票列表及关键指标
        """
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
                'selection_price': row.get('最新价', row.get('收盘', 0)),
                'change_pct': row.get('涨跌幅', 0),
                'rating': row.get('综合评级', ''),
                'composite_score': row.get('综合评分', 0),
                'fund_signal': row.get('资金信号', ''),
                'fund_consistency': row.get('资金一致性', ''),
                'relative_strength': row.get('相对强度', ''),
                'position_status': row.get('位置状态', ''),
                'turnover_rate': row.get('换手率', 0),
                'volume_ratio': row.get('量比', 0),
                'market_cap': row.get('流通市值_亿', 0)
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
        """
        将选股结果同时写入周记录文件
        每周一个文件，记录本周每天的选股结果
        """
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

    def get_consecutive_stocks(self, min_days=2):
        """
        获取连续被选中的股票
        min_days: 最少连续天数，默认2天
        返回：连续被选中的股票列表
        """
        if not HISTORY_FILE.exists():
            return []

        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history_index = json.load(f)

        batches = history_index.get('batches', [])
        if len(batches) < min_days:
            return []

        # 获取最近几天的选股记录
        recent_dates = []
        date_stocks = {}

        for batch in batches[:10]:  # 检查最近10个批次
            date = batch['selection_date']
            if date not in date_stocks:
                date_stocks[date] = set(batch['stock_codes'])
                recent_dates.append(date)

        if len(recent_dates) < min_days:
            return []

        # 按日期排序
        recent_dates = sorted(recent_dates, reverse=True)

        # 找出连续出现的股票
        consecutive_stocks = {}

        for i, date in enumerate(recent_dates):
            if i >= min_days - 1:
                # 检查从当前日期向前连续min_days天
                dates_to_check = recent_dates[i-min_days+1:i+1]
                if len(dates_to_check) == min_days:
                    # 检查是否为连续日期（工作日）
                    common_stocks = date_stocks[dates_to_check[0]]
                    for d in dates_to_check[1:]:
                        common_stocks = common_stocks.intersection(date_stocks[d])

                    for code in common_stocks:
                        if code not in consecutive_stocks:
                            consecutive_stocks[code] = {
                                'dates': dates_to_check,
                                'count': len(dates_to_check)
                            }
                        else:
                            # 更新为更长的连续天数
                            if len(dates_to_check) > consecutive_stocks[code]['count']:
                                consecutive_stocks[code] = {
                                    'dates': dates_to_check,
                                    'count': len(dates_to_check)
                                }

        # 只返回在今日选股结果中也存在的股票
        today_date = self.selection_date
        if today_date in date_stocks:
            today_stocks = date_stocks[today_date]
            result = []
            for code, info in consecutive_stocks.items():
                if code in today_stocks:
                    result.append({
                        'code': code,
                        'consecutive_days': info['count'],
                        'dates': info['dates']
                    })
            return sorted(result, key=lambda x: x['consecutive_days'], reverse=True)

        return []

    def analyze_last_week_performance(self):
        """
        周一执行时，分析上周选股结果的表现
        生成上周选股与当前股价对比的汇总报告
        """
        if not self.is_monday:
            return

        print("\n" + "=" * 70)
        print("📊 【上周选股表现回顾】周一汇总报告")
        print("=" * 70)

        # 获取上周的周编号
        last_week_dt = datetime.now() - timedelta(days=7)
        last_week_number = self._get_week_number(last_week_dt.strftime('%Y-%m-%d'))
        weekly_file = self._get_weekly_file_path(last_week_number)

        if not weekly_file.exists():
            print(f"\n❌ 未找到上周({last_week_number})的选股记录")
            return

        with open(weekly_file, 'r', encoding='utf-8') as f:
            weekly_data = json.load(f)

        print(f"\n📅 上周周期: {weekly_data['start_date']} ~ {weekly_data['end_date']}")
        print(f"📊 选股天数: {len(weekly_data['daily_records'])} 天")
        print(f"🔢 涉及股票: {len(weekly_data['all_stocks'])} 只")

        # 获取实时行情
        try:
            realtime_df = ak.stock_zh_a_spot_em()
        except Exception as e:
            print(f"\n❌ 获取实时行情失败: {e}")
            return

        # 分析每只股票的表现
        performance_results = []

        for code, stock_info in weekly_data['all_stocks'].items():
            current_data = realtime_df[realtime_df['代码'] == code]
            if current_data.empty:
                continue

            current_price = current_data['最新价'].values[0]
            today_change = current_data['涨跌幅'].values[0]

            # 获取首次被选中时的价格
            first_date = min(stock_info['appearances'])
            first_price = None

            for record in weekly_data['daily_records']:
                if record['date'] == first_date:
                    for s in record['stocks']:
                        if s['code'] == code:
                            first_price = s.get('price', 0)
                            break
                    break

            if first_price and first_price > 0:
                total_change = (current_price - first_price) / first_price * 100
            else:
                total_change = 0

            performance_results.append({
                'code': code,
                'name': stock_info['name'],
                'appear_count': stock_info['count'],
                'first_date': first_date,
                'first_price': first_price,
                'current_price': current_price,
                'total_change': total_change,
                'today_change': today_change
            })

        if not performance_results:
            print("\n⚠️ 无法获取股票行情数据")
            return

        # 按累计涨幅排序
        performance_results.sort(key=lambda x: x['total_change'], reverse=True)

        # 打印详细报告
        print("\n" + "-" * 70)
        print("📈 【上周选股表现明细】")
        print("-" * 70)
        print(f"{'代码':<8} {'名称':<8} {'出现次数':>8} {'首选价格':>10} {'当前价格':>10} {'累计涨幅':>10}")
        print("-" * 70)

        total_gain = []
        win_count = 0

        for r in performance_results:
            status = "🔥" if r['total_change'] > 5 else ("📈" if r['total_change'] > 0 else "📉")
            first_price_str = f"{r['first_price']:.2f}" if r['first_price'] else "N/A"
            print(f"{r['code']:<8} {r['name']:<8} {r['appear_count']:>8} {first_price_str:>10} "
                  f"{r['current_price']:>10.2f} {r['total_change']:>+9.2f}% {status}")

            if r['total_change'] != 0:
                total_gain.append(r['total_change'])
                if r['total_change'] > 0:
                    win_count += 1

        # 统计汇总
        print("\n" + "-" * 70)
        print("📊 【上周整体统计】")
        print("-" * 70)

        if total_gain:
            avg_gain = np.mean(total_gain)
            max_gain = max(total_gain)
            max_loss = min(total_gain)
            win_rate = win_count / len(total_gain) * 100

            print(f"   平均涨幅: {avg_gain:+.2f}%")
            print(f"   最大盈利: {max_gain:+.2f}%")
            print(f"   最大亏损: {max_loss:+.2f}%")
            print(f"   胜率: {win_rate:.1f}% ({win_count}/{len(total_gain)})")

        # 多次被选中的股票表现
        multi_select = [r for r in performance_results if r['appear_count'] >= 2]
        if multi_select:
            print("\n" + "-" * 70)
            print("⭐ 【多次被选中股票表现】(被选中≥2次)")
            print("-" * 70)

            multi_gains = [r['total_change'] for r in multi_select]
            avg_multi = np.mean(multi_gains)
            print(f"   数量: {len(multi_select)} 只")
            print(f"   平均涨幅: {avg_multi:+.2f}%")

            if avg_multi > avg_gain:
                print("   💡 多次选中股票跑赢整体，连续选中信号有效！")

        print("\n" + "=" * 70)

    def get_last_selection(self):
        """获取上一次的选股记录"""
        if not HISTORY_FILE.exists():
            return None

        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history_index = json.load(f)

        if not history_index.get('batches'):
            return None

        # 获取最近一次的批次
        last_batch = history_index['batches'][0]
        batch_file = HISTORY_DIR / last_batch['file_path']

        if batch_file.exists():
            with open(batch_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        return None

    def analyze_previous_selection(self):
        """
        分析上次选股结果的实际表现（v7.0新增核心功能）

        对比维度：
        1. 选股后次日涨跌幅
        2. 选股后累计涨跌幅（至今）
        3. 各评级股票的平均表现
        4. 策略有效性评估
        """
        print("\n" + "=" * 70)
        print("【历史选股回测分析】v7.0 策略验证")
        print("=" * 70)

        last_selection = self.get_last_selection()

        if last_selection is None:
            print("\n📊 暂无历史选股记录，跳过回测分析")
            print("   💡 本次选股完成后将自动保存记录")
            return

        selection_date = last_selection['selection_date']
        selection_time = last_selection['selection_time']
        batch_id = last_selection['batch_id']
        stocks = last_selection['stocks']

        print(f"\n📅 上次选股时间: {selection_time}")
        print(f"🔖 批次ID: {batch_id}")
        print(f"🎯 目标板块: {last_selection.get('target_sector') or '全市场'}")
        print(f"📊 选出股票数: {len(stocks)}")

        if not stocks:
            print("\n⚠️ 上次选股结果为空，跳过回测")
            return

        print(f"\n⏳ 正在获取 {len(stocks)} 只股票的最新行情...")

        # 获取实时行情数据
        try:
            realtime_df = ak.stock_zh_a_spot_em()
        except Exception as e:
            print(f"\n❌ 获取实时行情失败: {e}")
            return

        # 分析每只股票的表现
        analysis_results = []

        for stock in stocks:
            code = stock['code']
            name = stock['name']
            selection_price = stock.get('selection_price', 0)
            selection_rating = stock.get('rating', '')

            # 获取当前价格
            current_data = realtime_df[realtime_df['代码'] == code]

            if current_data.empty:
                continue

            current_price = current_data['最新价'].values[0]
            today_change = current_data['涨跌幅'].values[0]

            # 计算累计涨跌幅
            if selection_price and selection_price > 0:
                total_change = (current_price - selection_price) / selection_price * 100
            else:
                total_change = 0

            # 获取次日涨跌幅（需要历史数据）
            next_day_change = self._get_next_day_change(code, selection_date)

            analysis_results.append({
                'code': code,
                'name': name,
                'rating': selection_rating,
                'selection_price': selection_price,
                'current_price': current_price,
                'next_day_change': next_day_change,
                'total_change': total_change,
                'today_change': today_change
            })

        if not analysis_results:
            print("\n⚠️ 无法获取股票行情数据")
            return

        # 输出回测结果
        self._print_backtest_report(analysis_results, selection_date, batch_id)

    def _get_next_day_change(self, stock_code, selection_date):
        """获取选股后次日的涨跌幅"""
        try:
            # 获取选股日期后的历史数据
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = selection_date.replace('-', '')

            hist_data = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )

            if hist_data is None or len(hist_data) < 2:
                return None

            # 找到选股日期的索引
            hist_data['日期'] = pd.to_datetime(hist_data['日期']).dt.strftime('%Y-%m-%d')
            selection_idx = hist_data[hist_data['日期'] == selection_date].index

            if len(selection_idx) == 0:
                # 如果选股当日不是交易日，找最近的交易日
                return None

            idx = selection_idx[0]
            if idx + 1 < len(hist_data):
                # 次日涨跌幅
                next_day_close = hist_data.iloc[idx + 1]['收盘']
                selection_close = hist_data.iloc[idx]['收盘']
                return (next_day_close - selection_close) / selection_close * 100

            return None

        except Exception as e:
            return None

    def analyze_specific_batch_performance(self, batch_id):
        """
        分析指定批次选股结果的实际表现（v8.1新增）

        参数：
        - batch_id: 批次ID

        返回：
        - 分析结果字典
        """
        print("\n" + "=" * 70)
        print("【指定批次选股回测分析】v8.1")
        print("=" * 70)

        # 读取指定批次数据
        batch_file = HISTORY_DIR / f"batch_{batch_id}.json"

        if not batch_file.exists():
            print(f"\n❌ 批次 {batch_id} 不存在")
            return None

        with open(batch_file, 'r', encoding='utf-8') as f:
            batch_data = json.load(f)

        selection_date = batch_data['selection_date']
        selection_time = batch_data['selection_time']
        stocks = batch_data['stocks']

        print(f"\n📅 选股时间: {selection_time}")
        print(f"🔖 批次ID: {batch_id}")
        print(f"🎯 目标板块: {batch_data.get('target_sector') or '全市场'}")
        print(f"📊 选出股票数: {len(stocks)}")

        if not stocks:
            print("\n⚠️ 该批次选股结果为空")
            return None

        print(f"\n⏳ 正在获取 {len(stocks)} 只股票的最新行情...")

        # 获取实时行情数据
        try:
            realtime_df = ak.stock_zh_a_spot_em()
        except Exception as e:
            print(f"\n❌ 获取实时行情失败: {e}")
            return None

        # 分析每只股票的表现
        analysis_results = []

        for stock in stocks:
            code = stock['code']
            name = stock['name']
            selection_price = stock.get('selection_price', 0)
            selection_rating = stock.get('rating', '')

            # 获取当前价格
            current_data = realtime_df[realtime_df['代码'] == code]

            if current_data.empty:
                continue

            current_price = current_data['最新价'].values[0]
            today_change = current_data['涨跌幅'].values[0]

            # 计算累计涨跌幅
            if selection_price and selection_price > 0:
                total_change = (current_price - selection_price) / selection_price * 100
            else:
                total_change = 0

            # 获取次日涨跌幅（需要历史数据）
            next_day_change = self._get_next_day_change(code, selection_date)

            analysis_results.append({
                'code': code,
                'name': name,
                'rating': selection_rating,
                'selection_price': selection_price,
                'current_price': current_price,
                'next_day_change': next_day_change,
                'total_change': total_change,
                'today_change': today_change
            })

        if not analysis_results:
            print("\n⚠️ 无法获取股票行情数据")
            return None

        # 输出回测结果
        self._print_backtest_report(analysis_results, selection_date, batch_id)

        return analysis_results

    def _print_backtest_report(self, results, selection_date, batch_id):
        """打印回测报告"""
        print("\n" + "-" * 60)
        print("📈 【回测结果详情】")
        print("-" * 60)

        # 按评级分组统计
        rating_groups = {}
        for r in results:
            rating = r['rating'] or '未评级'
            if rating not in rating_groups:
                rating_groups[rating] = []
            rating_groups[rating].append(r)

        # 计算整体统计
        total_next_day = [r['next_day_change'] for r in results if r['next_day_change'] is not None]
        total_cumulative = [r['total_change'] for r in results if r['total_change'] != 0]

        # 显示每只股票的表现
        print("\n📋 个股表现明细:")
        print(f"{'代码':<8} {'名称':<8} {'评级':<12} {'次日涨幅':>10} {'累计涨幅':>10} {'今日涨幅':>10}")
        print("-" * 70)

        # 按累计涨幅排序
        results_sorted = sorted(results, key=lambda x: x['total_change'], reverse=True)

        for r in results_sorted:
            next_day_str = f"{r['next_day_change']:+.2f}%" if r['next_day_change'] is not None else "N/A"
            total_str = f"{r['total_change']:+.2f}%"
            today_str = f"{r['today_change']:+.2f}%"

            # 根据涨跌添加标识
            if r['total_change'] > 5:
                status = "🔥"
            elif r['total_change'] > 0:
                status = "📈"
            elif r['total_change'] > -5:
                status = "📉"
            else:
                status = "💔"

            print(f"{r['code']:<8} {r['name']:<8} {r['rating']:<12} {next_day_str:>10} {total_str:>10} {today_str:>10} {status}")

        # 分评级统计
        print("\n" + "-" * 60)
        print("📊 【分评级统计】")
        print("-" * 60)

        for rating in ['AAA(极强)', 'AA(强势)', 'A(良好)', 'B(一般)', 'C(较弱)', 'D(弱势)']:
            if rating in rating_groups:
                group = rating_groups[rating]
                next_day_changes = [r['next_day_change'] for r in group if r['next_day_change'] is not None]
                cumulative_changes = [r['total_change'] for r in group]

                avg_next_day = np.mean(next_day_changes) if next_day_changes else 0
                avg_cumulative = np.mean(cumulative_changes) if cumulative_changes else 0
                win_rate = len([c for c in cumulative_changes if c > 0]) / len(cumulative_changes) * 100 if cumulative_changes else 0

                print(f"   {rating}: {len(group)}只 | 次日均涨: {avg_next_day:+.2f}% | 累计均涨: {avg_cumulative:+.2f}% | 胜率: {win_rate:.1f}%")

        # 整体统计
        print("\n" + "-" * 60)
        print("📈 【整体表现统计】")
        print("-" * 60)

        if total_next_day:
            avg_next_day = np.mean(total_next_day)
            win_next_day = len([c for c in total_next_day if c > 0]) / len(total_next_day) * 100
            print(f"   次日平均涨幅: {avg_next_day:+.2f}%")
            print(f"   次日上涨比例: {win_next_day:.1f}%")

        if total_cumulative:
            avg_cumulative = np.mean(total_cumulative)
            max_gain = max(total_cumulative)
            max_loss = min(total_cumulative)
            win_rate = len([c for c in total_cumulative if c > 0]) / len(total_cumulative) * 100

            print(f"   累计平均涨幅: {avg_cumulative:+.2f}%")
            print(f"   最大盈利: {max_gain:+.2f}%")
            print(f"   最大亏损: {max_loss:+.2f}%")
            print(f"   累计胜率: {win_rate:.1f}%")

        # 策略评估
        print("\n" + "-" * 60)
        print("💡 【策略有效性评估】")
        print("-" * 60)

        if total_cumulative:
            if avg_cumulative > 3 and win_rate > 60:
                print("   ✅ 策略表现优秀！建议继续使用当前筛选逻辑")
            elif avg_cumulative > 0 and win_rate > 50:
                print("   📊 策略表现良好，可维持现有策略")
            elif avg_cumulative > -2:
                print("   ⚠️ 策略表现一般，建议优化筛选条件")
            else:
                print("   ❌ 策略表现不佳，建议检查市场环境或调整策略")

            # AAA级股票单独评估
            if 'AAA(极强)' in rating_groups:
                aaa_group = rating_groups['AAA(极强)']
                aaa_cumulative = [r['total_change'] for r in aaa_group]
                aaa_avg = np.mean(aaa_cumulative)
                print(f"\n   💎 AAA级标的表现: 平均涨幅 {aaa_avg:+.2f}%")
                if aaa_avg > avg_cumulative:
                    print("      → AAA级标的跑赢整体，评级系统有效")
                else:
                    print("      → AAA级未显著跑赢，可能需调整评分权重")

        print("\n" + "=" * 70)

    def print_header(self):
        """打印头部信息"""
        print("=" * 70)
        print("【A股次日冲高标的筛选系统 v8.1 - 精准剪枝版】")
        print(f"筛选日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔖 批次ID: {self.batch_id}")
        print("🆕 v8.1精准剪枝: 收紧筛选条件 + 综合评分阈值 + 风险收益比过滤 + 板块显示")
        print("⚡ 参数优化: 涨幅(-1%~5.5%) | 量比(≥1.2) | 换手率(10%~18%) | 市值(40~120亿)")
        print("🎯 最终筛选: 综合评分≥55 & 风险收益比≥1.5 & 最多20只")
        print("🚫 板块限制: 仅沪深主板（已排除创业板、科创板、北交所）")
        if self.is_monday:
            print("📅 今日是周一，将自动生成上周选股汇总报告")
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
            # 提取关键资金流向指标（注意：API返回的列名带有"今日"前缀）
            super_large_net = fund_data.get('今日超大单净流入-净额', 0)  # 超大单净流入净额
            large_net = fund_data.get('今日大单净流入-净额', 0)  # 大单净流入净额
            super_large_pct = fund_data.get('今日超大单净流入-净占比', 0)  # 超大单净流入占比
            large_pct = fund_data.get('今日大单净流入-净占比', 0)  # 大单净流入占比
            
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
            # 提取各类资金流向（注意：API返回的列名带有"今日"前缀）
            super_large_net = fund_data.get('今日超大单净流入-净额', 0)
            large_net = fund_data.get('今日大单净流入-净额', 0)
            medium_net = fund_data.get('今日中单净流入-净额', 0)
            small_net = fund_data.get('今日小单净流入-净额', 0)

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

    def calculate_composite_score(self, fund_consistency, fund_flow_ratio, rs_score, position_score, original_signal_strength, hot_money_score=0):
        """
        四维度综合评分系统（v9.1新增游资因子）

        理想强势标的需同时满足：
        1. 整体资金净流入与主力动向形成共振
        2. 走势强度明显超越大盘
        3. 股价已有效突破关键压力位并远离核心支撑区
        4. 【v9.1新增】游资活跃且处于适宜买入时机

        返回：(综合评分, 评级, 风险提示)
        """
        # 各维度权重 - v9.1优化：新增游资因子权重
        weight_hot_money = HOT_MONEY_CONFIG['weight_in_composite']  # v9.1新增：游资权重（默认15%）
        weight_fund = 0.35      # 资金流向权重（从45%降至35%）
        weight_rs = 0.25        # 相对强度权重（保持25%）
        weight_position = 0.15  # 价格位置权重（从20%降至15%）
        weight_original = 0.10  # 原有信号权重（保持10%）

        # 资金维度得分（一致性 + 流量占比）
        fund_score = (fund_consistency + fund_flow_ratio) / 2

        # 归一化各维度得分到0-100
        fund_normalized = max(0, min(100, (fund_score + 10) * 5))
        rs_normalized = max(0, min(100, (rs_score + 15) * 3.33))
        position_normalized = max(0, min(100, (position_score + 10) * 4))
        original_normalized = max(0, min(100, original_signal_strength * 10))
        hot_money_normalized = max(0, min(100, hot_money_score))  # v9.1新增：游资评分已经是0-100

        # 综合评分 - v9.1：新增游资因子
        composite = (
            fund_normalized * weight_fund +
            rs_normalized * weight_rs +
            position_normalized * weight_position +
            original_normalized * weight_original +
            hot_money_normalized * weight_hot_money  # v9.1新增
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

    # ========== v9.1新增：游资追踪分析模块 ==========

    def fetch_lhb_data(self, stock_code, lookback_days=30):
        """
        获取个股龙虎榜数据（v9.1新增）

        参数：
            stock_code: 股票代码
            lookback_days: 回溯天数

        返回：
            dict: {
                'appearances': 上榜次数,
                'records': 上榜记录列表,
                'buy_desks': 买方席位统计,
                'sell_desks': 卖方席位统计,
                'net_buy': 净买入金额
            }
        """
        try:
            # 构建缓存文件路径
            cache_file = HOT_MONEY_CACHE_DIR / f"lhb_{stock_code}_{datetime.now().strftime('%Y%m%d')}.json"

            # 检查缓存（当日缓存有效）
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)

            # 获取龙虎榜数据
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)

            result = {
                'appearances': 0,
                'records': [],
                'buy_desks': defaultdict(float),
                'sell_desks': defaultdict(float),
                'net_buy': 0
            }

            # 获取个股龙虎榜明细（东方财富接口）
            try:
                # 使用全局缓存，避免重复获取（每次分析都获取全市场数据会很慢）
                if self.lhb_cache is None:
                    # 第一次获取时，获取整个时间段的龙虎榜数据并缓存
                    print(f"      📊 正在获取{lookback_days}天龙虎榜数据（首次，稍后会缓存）...")
                    try:
                        self.lhb_cache = ak.stock_lhb_detail_em(
                            start_date=start_date.strftime('%Y%m%d'),
                            end_date=end_date.strftime('%Y%m%d')
                        )
                        if self.lhb_cache is not None and not self.lhb_cache.empty:
                            print(f"      ✅ 成功获取{len(self.lhb_cache)}条龙虎榜记录")
                        else:
                            print(f"      ⚠️ 近{lookback_days}天无龙虎榜数据")
                            self.lhb_cache = pd.DataFrame()  # 空DataFrame作为标记
                    except Exception as e:
                        print(f"      ⚠️ 获取龙虎榜数据失败: {str(e)[:50]}")
                        self.lhb_cache = pd.DataFrame()  # 空DataFrame作为标记

                # 从缓存中过滤出当前股票的记录
                df_lhb = None
                if self.lhb_cache is not None and not self.lhb_cache.empty:
                    # 可能的列名：'代码', '股票代码', 'symbol'
                    code_col = None
                    for col in ['代码', '股票代码', 'symbol']:
                        if col in self.lhb_cache.columns:
                            code_col = col
                            break

                    if code_col:
                        df_lhb = self.lhb_cache[self.lhb_cache[code_col] == stock_code].copy()

                if df_lhb is not None and not df_lhb.empty:
                    result['appearances'] = len(df_lhb)

                    for _, row in df_lhb.iterrows():
                        # 确保日期格式正确
                        date_val = row.get('上榜日期', '')
                        if pd.notna(date_val):
                            if isinstance(date_val, str):
                                date_str = date_val
                            else:
                                date_str = pd.to_datetime(date_val).strftime('%Y-%m-%d')
                        else:
                            date_str = ''

                        record = {
                            'date': date_str,
                            'reason': str(row.get('上榜原因', '')),
                            'close_price': float(row.get('收盘价', 0)) if pd.notna(row.get('收盘价')) else 0,
                            'change_pct': float(row.get('涨跌幅', 0)) if pd.notna(row.get('涨跌幅')) else 0,
                            'turnover': float(row.get('成交额', 0)) if pd.notna(row.get('成交额')) else 0,
                        }
                        result['records'].append(record)

                        # 统计买卖席位
                        for i in range(1, 6):  # 前5大买卖席位
                            buy_desk = row.get(f'买{i}营业部', '')
                            sell_desk = row.get(f'卖{i}营业部', '')
                            buy_amount_val = row.get(f'买{i}金额', 0)
                            sell_amount_val = row.get(f'卖{i}金额', 0)

                            # 安全转换金额
                            try:
                                buy_amount = float(buy_amount_val) if pd.notna(buy_amount_val) else 0
                                sell_amount = float(sell_amount_val) if pd.notna(sell_amount_val) else 0
                            except:
                                buy_amount = 0
                                sell_amount = 0

                            if buy_desk and buy_amount > 0:
                                result['buy_desks'][buy_desk] += buy_amount
                            if sell_desk and sell_amount > 0:
                                result['sell_desks'][sell_desk] += sell_amount

                    # 计算净买入
                    total_buy = sum(result['buy_desks'].values())
                    total_sell = sum(result['sell_desks'].values())
                    result['net_buy'] = total_buy - total_sell

                    # 转换defaultdict为普通dict以便JSON序列化
                    result['buy_desks'] = dict(result['buy_desks'])
                    result['sell_desks'] = dict(result['sell_desks'])

            except Exception as e:
                # 只有真正的错误才打印，如果只是没有数据则静默处理
                error_msg = str(e)
                if 'symbol' not in error_msg.lower() and 'not found' not in error_msg.lower():
                    pass  # 静默处理，很多股票可能没有龙虎榜数据

            # 保存缓存
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
            except:
                pass  # 缓存失败不影响主流程

            return result

        except Exception as e:
            # 只在调试时显示详细错误
            # print(f"      ⚠️ {stock_code}龙虎榜数据处理异常: {str(e)[:50]}")
            return {
                'appearances': 0,
                'records': [],
                'buy_desks': {},
                'sell_desks': {},
                'net_buy': 0
            }

    def calculate_hot_money_strength(self, lhb_data, stock_code):
        """
        计算游资强度评分（v9.1新增）

        评分维度：
        1. 上榜频率（30%）：近期上榜次数
        2. 知名游资参与度（30%）：知名游资席位介入程度
        3. 净买入强度（25%）：净买入金额占比
        4. 持续性（15%）：连续上榜天数

        返回：
            dict: {
                'total_score': 总分(0-100),
                'frequency_score': 频率得分,
                'reputation_score': 知名度得分,
                'net_buy_score': 净买入得分,
                'continuity_score': 持续性得分,
                'hot_money_desks': 介入的知名游资列表,
                'risk_level': 风险等级
            }
        """
        try:
            result = {
                'total_score': 0,
                'frequency_score': 0,
                'reputation_score': 0,
                'net_buy_score': 0,
                'continuity_score': 0,
                'hot_money_desks': [],
                'risk_level': '低'
            }

            if lhb_data['appearances'] == 0:
                return result

            # 1. 上榜频率评分（0-30分）
            appearances = lhb_data['appearances']
            if appearances >= 5:
                result['frequency_score'] = 30
            elif appearances >= 3:
                result['frequency_score'] = 25
            elif appearances >= 2:
                result['frequency_score'] = 15
            else:
                result['frequency_score'] = 5

            # 2. 知名游资参与度评分（0-30分）
            hot_money_involvement = 0
            buy_desks = lhb_data['buy_desks']

            for desk, amount in buy_desks.items():
                if desk in KNOWN_HOT_MONEY_DESKS:
                    desk_info = KNOWN_HOT_MONEY_DESKS[desk]
                    tier = desk_info['tier']

                    # 根据游资等级加分
                    if tier == 1:  # 一线游资
                        hot_money_involvement += 10
                        result['hot_money_desks'].append({
                            'name': desk,
                            'tier': '一线',
                            'style': desk_info['style'],
                            'amount': amount,
                            'success_rate': desk_info['success_rate']
                        })
                    elif tier == 2:  # 二线游资
                        hot_money_involvement += 6
                        result['hot_money_desks'].append({
                            'name': desk,
                            'tier': '二线',
                            'style': desk_info['style'],
                            'amount': amount,
                            'success_rate': desk_info['success_rate']
                        })
                    else:  # 机构
                        hot_money_involvement += 3
                        result['hot_money_desks'].append({
                            'name': desk,
                            'tier': '机构',
                            'style': desk_info['style'],
                            'amount': amount,
                            'success_rate': desk_info['success_rate']
                        })

            result['reputation_score'] = min(30, hot_money_involvement)

            # 3. 净买入强度评分（0-25分）
            net_buy = lhb_data['net_buy']
            if net_buy >= 50000000:  # 5000万以上
                result['net_buy_score'] = 25
            elif net_buy >= 30000000:  # 3000万以上
                result['net_buy_score'] = 20
            elif net_buy >= 10000000:  # 1000万以上
                result['net_buy_score'] = 15
            elif net_buy >= 5000000:  # 500万以上
                result['net_buy_score'] = 10
            elif net_buy > 0:
                result['net_buy_score'] = 5
            else:  # 净卖出
                result['net_buy_score'] = 0
                result['risk_level'] = '高'  # 净卖出风险较高

            # 4. 持续性评分（0-15分）
            records = lhb_data['records']
            if len(records) >= 2:
                # 检查连续上榜天数，过滤空日期
                dates = sorted([r['date'] for r in records if r['date']], reverse=True)
                continuous_days = 1

                for i in range(len(dates) - 1):
                    try:
                        date1 = datetime.strptime(dates[i], '%Y-%m-%d')
                        date2 = datetime.strptime(dates[i + 1], '%Y-%m-%d')
                        diff = (date1 - date2).days

                        if diff <= 3:  # 3天内视为连续
                            continuous_days += 1
                        else:
                            break
                    except:
                        break

                if continuous_days >= 4:
                    result['continuity_score'] = 15
                elif continuous_days >= 3:
                    result['continuity_score'] = 10
                elif continuous_days >= 2:
                    result['continuity_score'] = 6
                else:
                    result['continuity_score'] = 2

            # 计算总分
            result['total_score'] = (
                result['frequency_score'] +
                result['reputation_score'] +
                result['net_buy_score'] +
                result['continuity_score']
            )

            # 风险等级判断
            if net_buy < 0:
                result['risk_level'] = '高'
            elif result['total_score'] >= 70:
                result['risk_level'] = '低'
            elif result['total_score'] >= 50:
                result['risk_level'] = '中'
            else:
                result['risk_level'] = '中高'

            return result

        except Exception as e:
            print(f"      ⚠️ 计算游资强度异常: {str(e)[:50]}")
            return {
                'total_score': 0,
                'frequency_score': 0,
                'reputation_score': 0,
                'net_buy_score': 0,
                'continuity_score': 0,
                'hot_money_desks': [],
                'risk_level': '未知'
            }

    def assess_buy_timing(self, lhb_data, current_price, recent_high, recent_low):
        """
        评估买入时机（v9.1新增）

        判断游资当前操作阶段：
        - 建仓期：刚开始介入，价格相对较低
        - 加仓期：持续买入，价格温和上涨
        - 拉升期：价格快速上涨，成交放大
        - 出货期：开始卖出，价格高位震荡

        返回：
            dict: {
                'stage': 操作阶段,
                'timing_score': 时机得分(0-100),
                'recommendation': 操作建议,
                'reason': 判断理由
            }
        """
        try:
            result = {
                'stage': '观望',
                'timing_score': 0,
                'recommendation': '观望',
                'reason': ''
            }

            if lhb_data['appearances'] == 0:
                result['reason'] = '未发现游资介入'
                return result

            records = lhb_data['records']
            if not records:
                return result

            # 获取最近上榜记录
            latest_records = sorted(records, key=lambda x: x['date'], reverse=True)[:3]

            # 计算平均涨幅和价格位置
            avg_change = np.mean([r['change_pct'] for r in latest_records])
            price_position = (current_price - recent_low) / (recent_high - recent_low) if recent_high > recent_low else 0.5

            # 检查净买入趋势
            net_buy = lhb_data['net_buy']

            # 阶段判断逻辑
            if price_position < 0.3 and net_buy > 0:
                # 建仓期：低位 + 净买入
                result['stage'] = '建仓期'
                result['timing_score'] = 85
                result['recommendation'] = '积极关注'
                result['reason'] = f'游资低位建仓，价格位于底部区域({price_position*100:.1f}%)'

            elif 0.3 <= price_position < 0.6 and net_buy > HOT_MONEY_CONFIG['min_net_buy']:
                # 加仓期：中位 + 持续净买入
                result['stage'] = '加仓期'
                result['timing_score'] = 75
                result['recommendation'] = '适合跟进'
                result['reason'] = f'游资持续加仓，价格温和上涨({price_position*100:.1f}%)'

            elif 0.6 <= price_position < 0.85 and avg_change > 3:
                # 拉升期：中高位 + 快速上涨
                result['stage'] = '拉升期'
                result['timing_score'] = 60
                result['recommendation'] = '短线参与'
                result['reason'] = f'游资拉升中，追高风险较大({price_position*100:.1f}%)'

            elif price_position >= 0.85 or net_buy < 0:
                # 出货期：高位或净卖出
                result['stage'] = '出货期'
                result['timing_score'] = 20
                result['recommendation'] = '回避'
                result['reason'] = f'游资可能出货，风险较高({price_position*100:.1f}%位置)'

            else:
                # 不明确
                result['stage'] = '观望'
                result['timing_score'] = 40
                result['recommendation'] = '观望'
                result['reason'] = '游资意图不明确，建议观望'

            return result

        except Exception as e:
            print(f"      ⚠️ 评估买入时机异常: {str(e)[:50]}")
            return {
                'stage': '未知',
                'timing_score': 0,
                'recommendation': '观望',
                'reason': '数据异常'
            }

    def detect_risk_signals(self, lhb_data, stock_code):
        """
        识别游资撤退风险信号（v9.1新增）

        风险信号：
        1. 连续上榜后突然消失
        2. 知名游资大额卖出
        3. 净买入转为净卖出
        4. 高位放量滞涨

        返回：
            dict: {
                'has_risk': 是否有风险,
                'risk_signals': 风险信号列表,
                'risk_score': 风险评分(0-100, 越高越危险),
                'suggestion': 风险建议
            }
        """
        try:
            result = {
                'has_risk': False,
                'risk_signals': [],
                'risk_score': 0,
                'suggestion': ''
            }

            if lhb_data['appearances'] == 0:
                return result

            records = lhb_data['records']
            buy_desks = lhb_data['buy_desks']
            sell_desks = lhb_data['sell_desks']
            net_buy = lhb_data['net_buy']

            # 信号1：净卖出
            if net_buy < 0:
                result['risk_signals'].append('游资净卖出')
                result['risk_score'] += 40
                result['has_risk'] = True

            # 信号2：知名游资在卖方席位
            for desk, amount in sell_desks.items():
                if desk in KNOWN_HOT_MONEY_DESKS:
                    tier = KNOWN_HOT_MONEY_DESKS[desk]['tier']
                    if tier == 1:  # 一线游资卖出
                        result['risk_signals'].append(f'一线游资卖出：{desk[:20]}...')
                        result['risk_score'] += 30
                        result['has_risk'] = True
                    elif tier == 2:  # 二线游资卖出
                        result['risk_signals'].append(f'二线游资卖出：{desk[:20]}...')
                        result['risk_score'] += 15

            # 信号3：连续上榜后消失（最近3天无上榜）
            if len(records) >= 3:
                # 过滤空日期记录
                valid_records = [r for r in records if r['date']]
                if valid_records:
                    sorted_records = sorted(valid_records, key=lambda x: x['date'], reverse=True)
                    try:
                        latest_date = datetime.strptime(sorted_records[0]['date'], '%Y-%m-%d')
                        days_since_last = (datetime.now() - latest_date).days

                        if days_since_last >= 3:
                            result['risk_signals'].append(f'游资消失{days_since_last}天')
                            result['risk_score'] += 20
                            result['has_risk'] = True
                    except:
                        pass

            # 综合风险建议
            if result['risk_score'] >= 60:
                result['suggestion'] = '风险极高，建议立即离场'
            elif result['risk_score'] >= 40:
                result['suggestion'] = '风险较高，建议减仓或止损'
            elif result['risk_score'] >= 20:
                result['suggestion'] = '存在风险信号，密切关注'
            else:
                result['suggestion'] = '暂无明显风险'

            return result

        except Exception as e:
            print(f"      ⚠️ 检测风险信号异常: {str(e)[:50]}")
            return {
                'has_risk': False,
                'risk_signals': [],
                'risk_score': 0,
                'suggestion': '数据异常'
            }

    def analyze_hot_money_for_stock(self, stock_code, current_price, recent_high, recent_low):
        """
        综合分析个股游资情况（v9.1新增）

        整合所有游资分析模块，提供完整的游资画像

        返回：
            dict: 完整的游资分析结果
        """
        try:
            # 1. 获取龙虎榜数据
            lhb_data = self.fetch_lhb_data(stock_code, HOT_MONEY_CONFIG['lookback_days'])

            # 2. 计算游资强度
            strength = self.calculate_hot_money_strength(lhb_data, stock_code)

            # 3. 评估买入时机
            timing = self.assess_buy_timing(lhb_data, current_price, recent_high, recent_low)

            # 4. 检测风险信号
            risk = self.detect_risk_signals(lhb_data, stock_code)

            # 综合结果
            analysis = {
                'stock_code': stock_code,
                'lhb_appearances': lhb_data['appearances'],
                'net_buy_amount': lhb_data['net_buy'],
                'strength_score': strength['total_score'],
                'strength_detail': strength,
                'timing_score': timing['timing_score'],
                'timing_detail': timing,
                'risk_score': risk['risk_score'],
                'risk_detail': risk,
                'has_hot_money': lhb_data['appearances'] >= HOT_MONEY_CONFIG['min_appearances'],
                'is_active': lhb_data['appearances'] >= HOT_MONEY_CONFIG['min_appearances'] and lhb_data['net_buy'] > 0,
                '综合游资评分': self._calculate_final_hot_money_score(strength, timing, risk)
            }

            return analysis

        except Exception as e:
            print(f"      ⚠️ {stock_code}游资分析异常: {str(e)[:50]}")
            return {
                'stock_code': stock_code,
                'lhb_appearances': 0,
                'net_buy_amount': 0,
                'strength_score': 0,
                'timing_score': 0,
                'risk_score': 0,
                'has_hot_money': False,
                'is_active': False,
                '综合游资评分': 0
            }

    def _calculate_final_hot_money_score(self, strength, timing, risk):
        """
        计算最终游资综合评分（v9.1新增）

        综合考虑：强度、时机、风险

        返回：
            float: 0-100的综合评分
        """
        # 基础得分 = 强度得分 * 0.4 + 时机得分 * 0.4
        base_score = strength['total_score'] * 0.4 + timing['timing_score'] * 0.4

        # 风险惩罚：风险分越高，扣分越多
        risk_penalty = risk['risk_score'] * 0.3

        # 最终得分
        final_score = max(0, base_score - risk_penalty)

        return round(final_score, 2)

    # ========== v9.1 游资追踪模块结束 ==========

    def check_market_sentiment(self):
        """
        v8.0新增：市场情绪指标检查
        评估当日市场整体氛围，决定是否适合短线操作

        返回：(情绪分数0-100, 情绪状态, 详细数据)
        """
        print("\n" + "=" * 70)
        print("【v8.0 市场情绪检查】短线操作的前置条件")
        print("=" * 70)

        try:
            # 获取A股实时行情
            df_all = ak.stock_zh_a_spot_em()

            # 1. 涨停家数统计
            limit_up_count = len(df_all[df_all['涨跌幅'] >= 9.8])  # 接近涨停
            limit_down_count = len(df_all[df_all['涨跌幅'] <= -9.8])

            # 2. 连板股统计（涨停且量比>1的视为可能连板）
            potential_continuous = len(df_all[(df_all['涨跌幅'] >= 9.8) & (df_all['量比'] > 1)])

            # 3. 涨跌家数
            up_count = len(df_all[df_all['涨跌幅'] > 0])
            down_count = len(df_all[df_all['涨跌幅'] < 0])
            total_count = len(df_all)
            up_ratio = up_count / total_count * 100 if total_count > 0 else 0

            # 4. 两市成交额（亿元）
            total_turnover = df_all['成交额'].sum() / 1e8

            # 5. 大盘涨跌幅
            try:
                index_data = ak.stock_zh_index_spot_em()
                sh_index = index_data[index_data['代码'] == '000001']
                market_change = sh_index['涨跌幅'].values[0] if not sh_index.empty else 0
            except:
                market_change = 0

            # 情绪评分逻辑
            sentiment_score = 50  # 基础分

            # 涨停家数评分（最高30分）
            if limit_up_count >= 100:
                sentiment_score += 30
            elif limit_up_count >= 80:
                sentiment_score += 25
            elif limit_up_count >= 60:
                sentiment_score += 20
            elif limit_up_count >= 40:
                sentiment_score += 10
            elif limit_up_count < 20:
                sentiment_score -= 20

            # 涨跌比评分（最高20分）
            if up_ratio >= 70:
                sentiment_score += 20
            elif up_ratio >= 60:
                sentiment_score += 10
            elif up_ratio < 40:
                sentiment_score -= 15

            # 成交额评分（最高15分）
            if total_turnover >= 12000:  # 1.2万亿以上
                sentiment_score += 15
            elif total_turnover >= 10000:
                sentiment_score += 10
            elif total_turnover < 7000:
                sentiment_score -= 10

            # 大盘涨跌评分（最高15分）
            if market_change >= 2:
                sentiment_score += 15
            elif market_change >= 1:
                sentiment_score += 10
            elif market_change < -1:
                sentiment_score -= 10

            # 连板股加分（最高10分）
            if potential_continuous >= 15:
                sentiment_score += 10
            elif potential_continuous >= 10:
                sentiment_score += 5

            sentiment_score = max(0, min(100, sentiment_score))

            # 情绪状态判定
            if sentiment_score >= 75:
                sentiment_status = "极度亢奋"
                suggestion = "✅ 适合激进操作，妖股频出"
                color = "🟢"
            elif sentiment_score >= 60:
                sentiment_status = "情绪高涨"
                suggestion = "✅ 适合短线操作，可正常选股"
                color = "🟢"
            elif sentiment_score >= 45:
                sentiment_status = "情绪温和"
                suggestion = "⚠️ 可操作但需谨慎，降低仓位"
                color = "🟡"
            elif sentiment_score >= 30:
                sentiment_status = "情绪低迷"
                suggestion = "⚠️ 不适合激进操作，建议观望"
                color = "🟠"
            else:
                sentiment_status = "极度低迷"
                suggestion = "🔴 强烈建议空仓，市场风险极大"
                color = "🔴"

            # 打印情绪报告
            print(f"\n{color} 【市场情绪评分】: {sentiment_score:.0f}/100 - {sentiment_status}")
            print(f"   {suggestion}")
            print(f"\n   📊 市场数据:")
            print(f"      • 涨停家数: {limit_up_count} 只 | 跌停家数: {limit_down_count} 只")
            print(f"      • 潜在连板: {potential_continuous} 只")
            print(f"      • 涨跌比例: {up_count}涨 / {down_count}跌 ({up_ratio:.1f}%)")
            print(f"      • 两市成交: {total_turnover:.0f} 亿元")
            print(f"      • 上证指数: {market_change:+.2f}%")

            detail = {
                '涨停家数': limit_up_count,
                '跌停家数': limit_down_count,
                '连板股数': potential_continuous,
                '上涨家数': up_count,
                '下跌家数': down_count,
                '上涨比例': up_ratio,
                '成交额': total_turnover,
                '大盘涨幅': market_change
            }

            return sentiment_score, sentiment_status, detail

        except Exception as e:
            print(f"\n⚠️ 市场情绪检查失败: {e}")
            print("   跳过情绪过滤，继续选股流程")
            return 50, "无法判断", {}

    
    def step1_filter_by_change_pct(self, df):
        """第一步：涨幅区间筛选 (v8.1优化: -1% ~ 5.5%)"""
        print("\n" + "-" * 50)
        print("【第一步】涨幅区间筛选: -1% ≤ 涨幅 ≤ 5.5%")
        print("   💡 v8.1优化: 收紧区间，聚焦更稳健的标的")

        df_filtered = df[(df['涨跌幅'] >= -1) & (df['涨跌幅'] <= 5.5)].copy()

        # 排除ST股票
        df_filtered = df_filtered[~df_filtered['名称'].str.contains('ST|退', na=False)]

        # 排除北交所股票（8开头、4开头）
        df_filtered = df_filtered[~df_filtered['代码'].str.startswith(('8', '4'))]

        # v8.1新增：排除创业板股票（3开头）
        df_filtered = df_filtered[~df_filtered['代码'].str.startswith('3')]

        # v8.1新增：排除科创板股票（688开头）
        df_filtered = df_filtered[~df_filtered['代码'].str.startswith('688')]

        # 统计板块分布
        hushen_count = len(df_filtered[df_filtered['代码'].str.startswith(('6', '0'))])
        excluded_cyb = len(df[df['代码'].str.startswith('3')])
        excluded_kcb = len(df[df['代码'].str.startswith('688')])

        # 统计下跌股票数量
        pullback_count = len(df_filtered[df_filtered['涨跌幅'] < 0])
        strong_count = len(df_filtered[df_filtered['涨跌幅'] > 5])

        print(f"   ✅ 筛选后剩余: {len(df_filtered)} 只（仅沪深主板）")
        print(f"   ⚠️ 已排除: 创业板{excluded_cyb}只 | 科创板{excluded_kcb}只")
        if pullback_count > 0:
            print(f"   📉 包含回调股: {pullback_count} 只（捕捉反转机会）")
        if strong_count > 0:
            print(f"   📈 包含强势股: {strong_count} 只（涨幅5-5.5%）")
        return df_filtered

    def _calculate_monthly_gain(self, stock_code):
        """
        计算单只股票的月涨幅（供多线程调用）
        v8.0优化：增加强势股回调判断
        """
        try:
            hist_data = self.get_historical_data(stock_code, days=35)

            if hist_data is None or len(hist_data) < 20:
                return stock_code, None, None, True  # 数据不足，保留

            # 计算近一个月涨幅（20个交易日）
            if len(hist_data) >= 21:
                price_20d_ago = hist_data['收盘'].iloc[-21]
            else:
                price_20d_ago = hist_data['收盘'].iloc[0]

            current_price = hist_data['收盘'].iloc[-1]
            monthly_gain = (current_price - price_20d_ago) / price_20d_ago * 100

            # v8.0新增：判断近3日是否回调
            recent_3d_gain = 0
            if len(hist_data) >= 4:
                price_3d_ago = hist_data['收盘'].iloc[-4]
                recent_3d_gain = (current_price - price_3d_ago) / price_3d_ago * 100

            # 筛选逻辑：
            # 1. 月涨幅 < 30%（原逻辑）
            # 2. 月涨幅 20-50% 但近3日回调 < 5%（新增强势股回调逻辑）
            if monthly_gain < 30:
                is_qualified = True
                reason = "正常"
            elif 20 <= monthly_gain <= 50 and recent_3d_gain < 5:
                is_qualified = True
                reason = "强势回调"
            else:
                is_qualified = False
                reason = "月涨幅过高"

            return stock_code, monthly_gain, reason, is_qualified

        except Exception as e:
            return stock_code, None, None, True  # 出错时保守处理，保留

    def step1b_filter_by_monthly_gain(self, df):
        """
        第1.5步：月涨幅筛选 - v8.0优化版
        原逻辑：月涨幅 < 30%
        新增：允许月涨幅20-50%但近3日回调的强势股
        """
        print("\n" + "-" * 50)
        print("【第1.5步】月涨幅筛选: < 30% 或 (20-50%且近3日回调)")
        print("   💡 v8.0优化: 增加强势股回调逻辑，捕捉二次启动机会")
        print("   ⚡ 使用多线程加速处理")

        if df.empty:
            return df

        stock_codes = df['代码'].tolist()
        total = len(stock_codes)
        print(f"\n   ⏳ 正在并行计算 {total} 只股票的月涨幅...")

        # 存储结果：{stock_code: (monthly_gain, reason, is_qualified)}
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
                    stock_code, monthly_gain, reason, is_qualified = future.result()
                    results[stock_code] = (monthly_gain, reason, is_qualified)
                except Exception as e:
                    results[code] = (None, None, True)  # 出错保留

                completed += 1
                if completed % 100 == 0 or completed == total:
                    print(f"   ⏳ 已完成 {completed}/{total} ({completed*100//total}%)")

        # 根据结果筛选
        qualified_stocks = []
        strong_pullback_count = 0
        for idx, row in df.iterrows():
            stock_code = row['代码']
            monthly_gain, reason, is_qualified = results.get(stock_code, (None, None, True))

            if is_qualified:
                row_copy = row.copy()
                row_copy['月涨幅'] = monthly_gain
                row_copy['月涨幅类型'] = reason
                qualified_stocks.append(row_copy)
                if reason == "强势回调":
                    strong_pullback_count += 1

        df_filtered = pd.DataFrame(qualified_stocks)

        excluded_count = len(df) - len(df_filtered)
        print(f"\n   ✅ 筛选后剩余: {len(df_filtered)} 只")
        if strong_pullback_count > 0:
            print(f"   🔥 包含强势回调: {strong_pullback_count} 只（月涨幅20-50%但近期企稳）")
        if excluded_count > 0:
            print(f"   ⚠️ 已排除 {excluded_count} 只月涨幅过高且未回调的股票")

        return df_filtered

    def step2_filter_by_volume_ratio(self, df):
        """第二步：量比筛选 (v8.1优化: 量比 >= 1.2)"""
        print("\n" + "-" * 50)
        print("【第二步】热度筛选: 量比 ≥ 1.2")
        print("   💡 v8.1优化: 提高量比要求，过滤成交清淡标的")

        df_filtered = df[df['量比'] >= 1.2].copy()
        
        print(f"   ✅ 筛选后剩余: {len(df_filtered)} 只")
        return df_filtered
    
    def step3_filter_by_turnover(self, df):
        """第三步：换手率筛选 (v8.1优化: 10% ~ 18%)"""
        print("\n" + "-" * 50)
        print("【第三步】活跃度筛选: 10% ≤ 换手率 ≤ 18%")
        print("   💡 v8.1优化: 收紧区间，聚焦活跃但不过热的标的")

        df_filtered = df[(df['换手率'] >= 10) & (df['换手率'] <= 18)].copy()

        # 统计高换手率股票
        super_active = len(df_filtered[df_filtered['换手率'] >= 15])

        print(f"   ✅ 筛选后剩余: {len(df_filtered)} 只")
        if super_active > 0:
            print(f"   🔥 超活跃股: {super_active} 只（换手率≥15%）")
        return df_filtered
    
    def step4_filter_by_market_cap(self, df):
        """第四步：流通市值筛选 (v8.1优化: 40亿 ~ 120亿)"""
        print("\n" + "-" * 50)
        print("【第四步】规模筛选: 40亿 ≤ 流通市值 ≤ 120亿")
        print("   💡 v8.1优化: 收紧区间，兼顾流动性和稳定性")

        df['流通市值_亿'] = df['流通市值'] / 1e8
        df_filtered = df[(df['流通市值_亿'] >= 40) & (df['流通市值_亿'] <= 120)].copy()

        # 统计小盘股数量
        small_cap = len(df_filtered[df_filtered['流通市值_亿'] < 50])

        print(f"   ✅ 筛选后剩余: {len(df_filtered)} 只")
        if small_cap > 0:
            print(f"   📌 小盘股: {small_cap} 只（市值30-50亿，游资偏好）")
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
        """第九步：胜率筛选 (v8.0优化: 近20日上涨天数≥12天)"""
        print("\n" + "-" * 50)
        print("【第九步】胜率筛选: 近20个交易日上涨天数 ≥ 12天")
        print("   💡 v8.0优化: 从60日改为20日，更贴近短线动能")

        if df.empty:
            return df

        qualified_stocks = []

        for idx, row in df.iterrows():
            stock_code = row['代码']

            hist_data = self.get_historical_data(stock_code, days=30)
            if hist_data is None or len(hist_data) < 20:
                continue

            # 取最近20个交易日
            recent_20_days = hist_data.tail(20)

            # 计算涨跌情况
            recent_20_days['涨跌'] = recent_20_days['收盘'] - recent_20_days['开盘']

            up_days = len(recent_20_days[recent_20_days['涨跌'] > 0])
            down_days = len(recent_20_days[recent_20_days['涨跌'] < 0])

            # 近20日上涨天数≥12天（胜率60%）
            if up_days >= 12:
                row_copy = row.copy()
                row_copy['上涨天数'] = up_days
                row_copy['下跌天数'] = down_days
                row_copy['胜率'] = f"{up_days}/20"
                row_copy['胜率百分比'] = up_days / 20 * 100
                qualified_stocks.append(row_copy)

        df_filtered = pd.DataFrame(qualified_stocks)
        if not df_filtered.empty:
            print(f"   ✅ 筛选后剩余: {len(df_filtered)} 只")
            avg_up = df_filtered['上涨天数'].mean() if '上涨天数' in df_filtered.columns else 0
            avg_win_rate = df_filtered['胜率百分比'].mean() if '胜率百分比' in df_filtered.columns else 0
            print(f"   📊 平均上涨天数: {avg_up:.1f} 天 | 平均胜率: {avg_win_rate:.1f}%")
            # 统计超高胜率股票
            super_high = len(df_filtered[df_filtered['上涨天数'] >= 15])
            if super_high > 0:
                print(f"   🔥 超强势股: {super_high} 只（近20日上涨≥15天）")
        else:
            print(f"   ✅ 筛选后剩余: 0 只")

        return df_filtered
    
    def identify_sector_leader(self, stock_code, stock_name, current_change, turnover_amount, df_all_sector):
        """
        v8.0新增：识别板块龙头
        判断该股票在其所属板块中的地位

        返回：(是否龙头, 龙头等级, 详细信息)
        """
        if df_all_sector is None or df_all_sector.empty:
            return False, "未知", {}

        try:
            # 在板块内的排名
            stock_row = df_all_sector[df_all_sector['代码'] == stock_code]
            if stock_row.empty:
                return False, "未知", {}

            # 板块内涨幅排名
            change_rank = (df_all_sector['涨跌幅'] > current_change).sum() + 1
            change_percentile = change_rank / len(df_all_sector) * 100

            # 板块内成交额排名
            turnover_rank = (df_all_sector['成交额'] > turnover_amount).sum() + 1
            turnover_percentile = turnover_rank / len(df_all_sector) * 100

            # 龙头判定逻辑
            is_leader = False
            leader_level = "跟随股"

            if change_rank <= 3 and turnover_rank <= 3:
                # 涨幅和成交额都在前3
                is_leader = True
                leader_level = "超级龙头"
            elif change_rank <= 5 and turnover_rank <= 10:
                # 涨幅前5，成交额前10
                is_leader = True
                leader_level = "龙头"
            elif change_rank <= 10:
                # 涨幅前10
                leader_level = "准龙头"

            detail = {
                '涨幅排名': change_rank,
                '涨幅百分位': change_percentile,
                '成交额排名': turnover_rank,
                '成交额百分位': turnover_percentile,
                '板块总数': len(df_all_sector),
                '龙头等级': leader_level
            }

            return is_leader, leader_level, detail

        except Exception as e:
            return False, "未知", {}

    def calculate_risk_reward_ratio(self, stock_code, current_price, hist_data):
        """
        v8.0新增：计算风险收益比
        基于技术位置计算止损位和止盈位

        返回：(止损位, 止盈位, 风险收益比, 详细信息)
        """
        try:
            if hist_data is None or len(hist_data) < 20:
                return 0, 0, 0, {}

            # 计算均线
            hist_data['MA5'] = hist_data['收盘'].rolling(window=5).mean()
            hist_data['MA10'] = hist_data['收盘'].rolling(window=10).mean()
            hist_data['MA20'] = hist_data['收盘'].rolling(window=20).mean()

            latest = hist_data.iloc[-1]
            ma5 = latest['MA5']
            ma10 = latest['MA10']
            ma20 = latest['MA20']

            # 近20日低点和高点
            recent_20 = hist_data.tail(20)
            recent_low = recent_20['最低'].min()
            recent_high = recent_20['最高'].max()

            # === 止损位计算 ===
            # 1. 短线止损：跌破MA5或-3%
            stop_loss_ma5 = ma5
            stop_loss_pct = current_price * 0.97

            # 2. 技术止损：跌破近期低点
            stop_loss_tech = recent_low * 0.98

            # 取最高的止损位（最保守）
            stop_loss = max(stop_loss_ma5, stop_loss_pct, stop_loss_tech)

            # === 止盈位计算 ===
            # 1. 短线止盈：+5%或+8%
            take_profit_5pct = current_price * 1.05
            take_profit_8pct = current_price * 1.08

            # 2. 技术止盈：突破近期高点
            take_profit_tech = recent_high * 1.02

            # 取最高的止盈位（最激进）
            take_profit = max(take_profit_5pct, take_profit_tech)

            # === 风险收益比 ===
            potential_profit = take_profit - current_price
            potential_loss = current_price - stop_loss

            if potential_loss > 0:
                risk_reward_ratio = potential_profit / potential_loss
            else:
                risk_reward_ratio = 0

            # 止损止盈百分比
            stop_loss_pct_val = (stop_loss - current_price) / current_price * 100
            take_profit_pct_val = (take_profit - current_price) / current_price * 100

            detail = {
                '当前价': current_price,
                '止损位': stop_loss,
                '止盈位': take_profit,
                '止损幅度': stop_loss_pct_val,
                '止盈幅度': take_profit_pct_val,
                '风险收益比': risk_reward_ratio,
                'MA5': ma5,
                'MA10': ma10,
                'MA20': ma20,
                '近期低点': recent_low,
                '近期高点': recent_high
            }

            return stop_loss, take_profit, risk_reward_ratio, detail

        except Exception as e:
            return 0, 0, 0, {}

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
        第十一步：四维度综合分析（v9.1新增游资追踪）
        整合：资金共振 + 市场相对强度 + 关键价格位置 + 游资动向
        v9.1新增：游资追踪分析及评分
        """
        print("\n" + "-" * 50)
        print("【第十一步】🎯 四维度综合分析（v9.1新增游资追踪）")
        print("   📊 维度1: 资金共振（主力+整体一致性）")
        print("   📈 维度2: 市场相对强度（跑赢大盘）")
        print("   📍 维度3: 关键价格位置（突破+支撑）")
        print("   💰 维度4: 游资动向（龙虎榜+买入时机）【v9.1新增】")
        print("   🔥 筛选标准: 综合评分≥55 + 风险收益比≥1.5")

        if df.empty:
            return df

        print(f"\n   ⏳ 正在进行 {len(df)} 只股票的多维度深度分析...")

        # 获取全市场数据用于板块龙头识别
        try:
            df_all_market = ak.stock_zh_a_spot_em()
        except:
            df_all_market = None

        qualified_stocks = []
        processed_count = 0

        for idx, row in df.iterrows():
            stock_code = row['代码']
            stock_name = row['名称']
            current_change = row['涨跌幅']
            current_price = row.get('最新价', row.get('收盘', 0))
            turnover_amount = row.get('成交额', 0)

            processed_count += 1
            if processed_count % 5 == 0:
                print(f"   ⏳ 已完成 {processed_count}/{len(df)} 只...")

            # === 维度2：市场相对强度分析 ===
            rs_score, rs_detail = self.analyze_relative_strength(stock_code, stock_name, current_change)

            # === 维度3：关键价格位置分析 ===
            position_score, position_detail = self.analyze_price_position(stock_code, stock_name)

            # === v8.0新增：板块龙头识别 ===
            is_leader, leader_level, leader_detail = self.identify_sector_leader(
                stock_code, stock_name, current_change, turnover_amount, df_all_market
            )

            # === v8.0新增：风险收益比计算 ===
            hist_data = self.get_historical_data(stock_code, days=30)
            stop_loss, take_profit, risk_reward, rr_detail = self.calculate_risk_reward_ratio(
                stock_code, current_price, hist_data
            )

            # === v9.1新增：游资追踪分析 ===
            hot_money_analysis = {}
            if hist_data is not None and len(hist_data) >= 20:
                # akshare返回的列名是中文的
                recent_high = hist_data['最高'].tail(60).max() if len(hist_data) >= 60 else hist_data['最高'].max()
                recent_low = hist_data['最低'].tail(60).min() if len(hist_data) >= 60 else hist_data['最低'].min()
                hot_money_analysis = self.analyze_hot_money_for_stock(
                    stock_code, current_price, recent_high, recent_low
                )
            else:
                # 数据不足，使用默认值
                hot_money_analysis = {
                    'stock_code': stock_code,
                    'lhb_appearances': 0,
                    'net_buy_amount': 0,
                    'strength_score': 0,
                    'timing_score': 0,
                    'risk_score': 0,
                    'has_hot_money': False,
                    'is_active': False,
                    '综合游资评分': 0,
                    'strength_detail': {},
                    'timing_detail': {},
                    'risk_detail': {}
                }

            # === 综合评分 ===
            fund_consistency = row.get('一致性得分', 0)
            fund_flow_ratio = row.get('流量占比得分', 0)
            original_signal_strength = row.get('信号强度', 0)
            hot_money_score = hot_money_analysis.get('综合游资评分', 0)

            composite_score, rating, risk_warning, contradictions = self.calculate_composite_score(
                fund_consistency, fund_flow_ratio, rs_score, position_score, original_signal_strength, hot_money_score
            )

            # v8.1新增：获取股票所属板块/行业
            sector_info = ""
            try:
                sector_info = self.get_stock_concepts(stock_code)
                if not sector_info:
                    sector_info = "未知板块"
            except:
                sector_info = "未知板块"

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
            # v8.0新增字段
            row_copy['是否龙头'] = is_leader
            row_copy['龙头等级'] = leader_level
            row_copy['涨幅排名'] = leader_detail.get('涨幅排名', 0)
            row_copy['止损位'] = stop_loss
            row_copy['止盈位'] = take_profit
            row_copy['风险收益比'] = risk_reward
            row_copy['止损幅度'] = rr_detail.get('止损幅度', 0)
            row_copy['止盈幅度'] = rr_detail.get('止盈幅度', 0)
            # v8.1新增字段
            row_copy['所属板块'] = sector_info
            # v9.1新增字段：游资追踪
            row_copy['游资评分'] = hot_money_score
            row_copy['龙虎榜次数'] = hot_money_analysis.get('lhb_appearances', 0)
            row_copy['游资净买入'] = hot_money_analysis.get('net_buy_amount', 0)
            row_copy['游资强度'] = hot_money_analysis.get('strength_score', 0)
            row_copy['买入时机'] = hot_money_analysis.get('timing_score', 0)
            row_copy['游资风险'] = hot_money_analysis.get('risk_score', 0)
            row_copy['有游资'] = hot_money_analysis.get('has_hot_money', False)
            row_copy['游资活跃'] = hot_money_analysis.get('is_active', False)
            row_copy['游资阶段'] = hot_money_analysis.get('timing_detail', {}).get('stage', '观望')
            row_copy['游资建议'] = hot_money_analysis.get('timing_detail', {}).get('recommendation', '观望')
            row_copy['游资风险提示'] = hot_money_analysis.get('risk_detail', {}).get('suggestion', '')

            # v8.1新增：剪枝逻辑 - 只保留综合评分≥55且风险收益比≥1.5的股票
            if composite_score >= 55 and risk_reward >= 1.5:
                qualified_stocks.append(row_copy)

        df_result = pd.DataFrame(qualified_stocks)

        if not df_result.empty:
            # v9.1优化：优先展示游资活跃的股票，然后按综合评分排序
            df_result['排序权重'] = df_result['综合评分'] + df_result['游资活跃'].astype(int) * 5  # 游资活跃加5分权重
            df_result = df_result.sort_values(['游资活跃', '排序权重'], ascending=[False, False])
            df_result = df_result.drop('排序权重', axis=1)  # 删除临时列

            # v8.1新增：限制最终输出数量为前20只
            original_count = len(df_result)
            if len(df_result) > 20:
                df_result = df_result.head(20)
                print(f"\n   🎯 v8.1剪枝: 从{original_count}只筛选出综合评分最高的前20只")

            # 统计评级分布
            aaa_count = len(df_result[df_result['综合评级'].str.startswith('AAA')])
            aa_count = len(df_result[df_result['综合评级'].str.startswith('AA') & ~df_result['综合评级'].str.startswith('AAA')])
            a_count = len(df_result[df_result['综合评级'].str.startswith('A') & ~df_result['综合评级'].str.startswith('AA')])

            # 统计相对强度
            strong_rs = len(df_result[df_result['相对强度'].isin(['显著强势', '相对强势'])])

            # 统计价格位置
            good_position = len(df_result[df_result['位置状态'].isin(['突破确认+支撑稳固', '位置良好'])])

            # v8.0新增统计
            leader_count = len(df_result[df_result['是否龙头'] == True])
            super_leader = len(df_result[df_result['龙头等级'] == '超级龙头'])
            good_rr = len(df_result[df_result['风险收益比'] >= 2])
            excellent_rr = len(df_result[df_result['风险收益比'] >= 3])

            # v9.1新增：游资统计
            hot_money_active = len(df_result[df_result['游资活跃'] == True])
            hot_money_present = len(df_result[df_result['有游资'] == True])
            building_stage = len(df_result[df_result['游资阶段'] == '建仓期'])
            accumulating_stage = len(df_result[df_result['游资阶段'] == '加仓期'])

            print(f"\n   ✅ 四维度分析完成: {len(df_result)} 只 (已过滤: 综合评分≥55 & 风险收益比≥1.5)")
            print(f"   🏆 综合评级: AAA={aaa_count} | AA={aa_count} | A={a_count}")
            print(f"   📈 相对强势: {strong_rs} 只跑赢大盘")
            print(f"   📍 位置良好: {good_position} 只处于有利位置")
            print(f"   🔥 龙头情况: 龙头={leader_count}只(超级龙头={super_leader}) | 风险收益比≥2={good_rr}只(≥3={excellent_rr}只)")
            print(f"   💰 v9.1游资: 活跃={hot_money_active}只 | 有介入={hot_money_present}只 | 建仓期={building_stage}只 | 加仓期={accumulating_stage}只")

            if aaa_count > 0:
                print(f"   ⭐⭐⭐ 发现 {aaa_count} 只【四维共振】顶级标的！")
            if super_leader > 0:
                print(f"   👑 发现 {super_leader} 只【超级龙头】股！")
            if hot_money_active > 0:
                print(f"   💸 发现 {hot_money_active} 只【游资活跃】股！")
        else:
            print(f"   ✅ 分析完成: 0 只 (所有股票均未达到: 综合评分≥55 & 风险收益比≥1.5)")

        return df_result
    
    def run(self, sector_codes=None):
        """执行完整筛选流程（v8.0优化版）"""
        self.print_header()

        # 【v8.0新增】市场情绪检查
        sentiment_score, sentiment_status, sentiment_detail = self.check_market_sentiment()

        # 情绪过滤：低于30分时给出强烈警告
        if sentiment_score < 30:
            print("\n" + "🔴" * 35)
            print("⚠️  市场情绪极度低迷，强烈建议空仓观望！")
            print("   继续选股风险极大，请谨慎决策")
            print("🔴" * 35)
            user_input = input("\n是否继续选股？(输入yes继续，其他键退出): ").strip().lower()
            if user_input != 'yes':
                print("\n✅ 已退出选股流程，空仓观望是最好的策略")
                return
        elif sentiment_score < 45:
            print("\n" + "🟠" * 35)
            print("⚠️  市场情绪偏弱，建议降低仓位或观望")
            print("   即使选出股票，也应轻仓试探")
            print("🟠" * 35)

        # 【v7.0新增】周一时先进行上周汇总报告
        if self.is_monday:
            self.analyze_last_week_performance()

        # 【v7.0新增】先进行历史回测分析
        self.analyze_previous_selection()

        print("\n" + "=" * 70)
        print("【开始本次选股筛选】")
        print("=" * 70)

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
        """输出筛选结果（v7.0升级版 - 三维度展示 + 历史记录 + 连续选中标识）"""
        print("\n" + "=" * 70)
        print("【筛选结果】v7.0 三维度综合分析")
        print("=" * 70)

        if df.empty:
            print("\n🔴 今日暂无符合条件的标的")
            print("\n💡 提示: 严格遵循首要原则 - 无标的满足则当日放弃，不强行开仓")
        else:
            # 获取连续选中的股票（需要先保存当前结果才能检测）
            consecutive_stocks = {}

            # 先保存选股结果，以便检测连续选中
            self.save_selection_result(df)

            # 检测连续选中的股票
            consecutive_list = self.get_consecutive_stocks(min_days=2)
            for item in consecutive_list:
                consecutive_stocks[item['code']] = item['consecutive_days']

            # 在df中标记连续选中的股票
            df['连续选中天数'] = df['代码'].apply(lambda x: consecutive_stocks.get(x, 0))
            sector_info = f"【{self.target_sector}】板块内" if self.target_sector else ""
            print(f"\n🟢 {sector_info}共筛选出 {len(df)} 只潜在次日冲高标的")

            # ========== 连续选中股票特别提示 ==========
            consecutive_df = df[df['连续选中天数'] >= 2].copy()
            if not consecutive_df.empty:
                consecutive_df = consecutive_df.sort_values('连续选中天数', ascending=False)
                print(f"\n{'🔥'*20}")
                print(f"🌟🌟🌟 【重点关注 - 连续选中股票】共 {len(consecutive_df)} 只 🌟🌟🌟")
                print(f"💡 这些股票连续2天以上被选中，走势持续良好！")
                print(f"{'🔥'*20}")

                for idx, row in consecutive_df.iterrows():
                    days = int(row['连续选中天数'])
                    stars = "⭐" * min(days, 5)
                    current_price = row.get('最新价', row.get('收盘', 0))
                    print(f"\n  {stars} {row['代码']} | {row['名称']} | 连续 {days} 天被选中")
                    print(f"      💰 当前价: {current_price:.2f}元 | 涨幅: {row['涨跌幅']:.2f}% | 评级: {row['综合评级']}")
                    print(f"      📊 资金: {row.get('资金一致性', '未知')} | 强度: {row.get('相对强度', '未知')} | 位置: {row.get('位置状态', '未知')}")

                print(f"\n{'='*60}")

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
        print("    v7.0 三维度分析旨在降低风险，但不能完全规避")
        print("    投资有风险，入市需谨慎")
        print("=" * 70)

    def _print_stock_detail(self, row, level='A'):
        """打印个股详细信息（v8.0优化版 - 含龙头标识和止损止盈）"""
        # 根据级别选择图标
        icons = {
            'AAA': '🔥',
            'AA': '📈',
            'A': '📌',
            'other': '📋'
        }
        icon = icons.get(level, '📋')

        # 获取当前股价
        current_price = row.get('最新价', row.get('收盘', 0))

        # 连续选中标识
        consecutive_days = row.get('连续选中天数', 0)
        consecutive_tag = f" 🔥连续{int(consecutive_days)}天" if consecutive_days >= 2 else ""

        # v8.0新增：龙头标识
        leader_level = row.get('龙头等级', '')
        leader_tag = ""
        if leader_level == '超级龙头':
            leader_tag = " 👑超级龙头"
        elif leader_level == '龙头':
            leader_tag = " 🏆龙头"
        elif leader_level == '准龙头':
            leader_tag = " ⭐准龙头"

        # v8.1新增：板块信息
        sector = row.get('所属板块', '未知板块')

        print(f"\n  {icon} {row['代码']} | {row['名称']} | 💰当前价: {current_price:.2f}元{consecutive_tag}{leader_tag}")
        print(f"     🏆 综合评级: {row['综合评级']} | 评分: {row['综合评分']:.1f}")
        print(f"     🏢 所属板块: {sector}")

        # 基础数据
        monthly_gain_type = row.get('月涨幅类型', '')
        monthly_tag = f" ({monthly_gain_type})" if monthly_gain_type == '强势回调' else ""
        print(f"     📊 涨幅: {row['涨跌幅']:.2f}% | 量比: {row['量比']:.2f} | "
              f"换手率: {row['换手率']:.2f}% | 流通市值: {row['流通市值_亿']:.1f}亿{monthly_tag}")

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

        # v9.1新增：游资动向（维度4）
        hot_money_score = row.get('游资评分', 0)
        hot_money_active = row.get('游资活跃', False)
        lhb_count = row.get('龙虎榜次数', 0)
        hot_money_stage = row.get('游资阶段', '观望')
        hot_money_recommendation = row.get('游资建议', '观望')
        if lhb_count > 0 or hot_money_active:
            net_buy = row.get('游资净买入', 0) / 1e8  # 转换为亿元
            active_tag = "🔥活跃" if hot_money_active else ""
            stage_icon = {"建仓期": "🟢", "加仓期": "🟡", "拉升期": "🟠", "出货期": "🔴"}.get(hot_money_stage, "⚪")
            print(f"     💰 游资动向: 评分{hot_money_score:.1f} | 上榜{lhb_count}次 | 净买入{net_buy:.2f}亿 {active_tag}")
            print(f"     💸 操作阶段: {stage_icon}{hot_money_stage} | 建议: {hot_money_recommendation}")

        # v8.0新增：止损止盈和风险收益比
        stop_loss = row.get('止损位', 0)
        take_profit = row.get('止盈位', 0)
        risk_reward = row.get('风险收益比', 0)
        stop_loss_pct = row.get('止损幅度', 0)
        take_profit_pct = row.get('止盈幅度', 0)
        if stop_loss > 0 and take_profit > 0:
            rr_status = "优秀" if risk_reward >= 3 else ("良好" if risk_reward >= 2 else "一般")
            print(f"     ⚖️  止损: {stop_loss:.2f}元({stop_loss_pct:+.1f}%) | "
                  f"止盈: {take_profit:.2f}元({take_profit_pct:+.1f}%) | "
                  f"风险收益比: {risk_reward:.2f} ({rr_status})")

        # 风险提示
        risk = row.get('风险提示', '')
        if risk and not risk.startswith('✅'):
            print(f"     {risk}")

        # 胜率信息（v8.0改为20日）
        if '胜率' in row and pd.notna(row.get('胜率')):
            win_rate_pct = row.get('胜率百分比', 0)
            print(f"     📊 近20日胜率: {row['胜率']} ({win_rate_pct:.0f}%) | "
                  f"上涨{row['上涨天数']}天 vs 下跌{row['下跌天数']}天")

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


def show_weekly_records():
    """显示周记录列表"""
    print("\n" + "=" * 70)
    print("📅 【周选股记录】")
    print("=" * 70)

    if not WEEKLY_DIR.exists():
        print("\n暂无周记录")
        return

    weekly_files = sorted(WEEKLY_DIR.glob("week_*.json"), reverse=True)
    if not weekly_files:
        print("\n暂无周记录")
        return

    print(f"\n共有 {len(weekly_files)} 周记录:\n")
    print(f"{'序号':<6} {'周编号':<15} {'日期范围':<25} {'选股天数':>8} {'涉及股票':>8}")
    print("-" * 70)

    for i, wf in enumerate(weekly_files[:12], 1):  # 只显示最近12周
        with open(wf, 'r', encoding='utf-8') as f:
            data = json.load(f)
        date_range = f"{data.get('start_date', 'N/A')} ~ {data.get('end_date', 'N/A')}"
        print(f"{i:<6} {data['week_number']:<15} {date_range:<25} {len(data['daily_records']):>8} {len(data['all_stocks']):>8}")

    print("\n" + "=" * 70)


def show_history_list():
    """显示历史选股记录列表（v8.1优化：增加二级菜单和对比分析）"""
    print("\n" + "=" * 70)
    print("📚 【历史选股记录】v8.1")
    print("=" * 70)

    if not HISTORY_FILE.exists():
        print("\n暂无历史选股记录")
        return

    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        history_index = json.load(f)

    batches = history_index.get('batches', [])
    if not batches:
        print("\n暂无历史选股记录")
        return

    print(f"\n共有 {len(batches)} 条历史记录:\n")
    print(f"{'序号':<6} {'批次ID':<20} {'选股时间':<22} {'板块':<12} {'股票数':>6}")
    print("-" * 70)

    for i, batch in enumerate(batches, 1):
        sector = batch.get('target_sector') or '全市场'
        print(f"{i:<6} {batch['batch_id']:<20} {batch['selection_time']:<22} {sector:<12} {batch['stock_count']:>6}")

    print("\n" + "=" * 70)

    # 二级菜单：选择查看详情
    while True:
        try:
            choice = input("\n💡 输入序号查看该批次详情并对比当前股价 (输入0返回): ").strip()

            if choice == '0' or choice == '':
                break

            choice_num = int(choice)
            if 1 <= choice_num <= len(batches):
                selected_batch = batches[choice_num - 1]
                batch_id = selected_batch['batch_id']

                # 调用对比分析
                screener = StockScreener()
                screener.analyze_specific_batch_performance(batch_id)

                # 询问是否继续查看其他批次
                cont = input("\n是否继续查看其他批次？(y/n，默认n): ").strip().lower()
                if cont != 'y':
                    break
            else:
                print(f"⚠️ 请输入1-{len(batches)}之间的序号")
        except ValueError:
            print("⚠️ 请输入有效的数字")
        except Exception as e:
            print(f"⚠️ 发生错误: {e}")
            break


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("【A股次日冲高标的筛选系统 v9.1 - 游资追踪版】")
    print("  🆕 v9.1游资追踪: 龙虎榜分析 + 游资强度评分 + 买入时机判断 + 风险预警")
    print("  ⚡ 参数优化: 涨幅(-1%~5.5%) | 量比(≥1.2) | 换手率(10%~18%) | 市值(40~120亿)")
    print("  🎯 最终筛选: 综合评分≥55 & 风险收益比≥1.5 & 最多20只")
    print("  🚫 板块限制: 仅沪深主板（已排除创业板、科创板、北交所）")
    print("  💰 权重调整: 游资15% + 资金35% + 相对强度25% + 价格位置15% + 原信号10%")
    print("  📊 四维度综合分析: 资金共振 + 相对强度 + 关键价格位置 + 游资动向")
    print("  🔥 优先展示: 游资活跃且综合评分高的股票优先排序")
    print("=" * 70)
    print("\n请选择操作:")
    print("  1. 全市场筛选（默认）- 自动回测上次结果")
    print("  2. 指定板块/概念筛选 - 自动回测上次结果")
    print("  3. 查看所有概念板块")
    print("  4. 查看所有行业板块")
    print("  5. 查看全年主题日历")
    print("  6. 查看历史选股记录 🆕 [支持选择批次回测对比]")
    print("  7. 查看周选股记录")

    try:
        choice = input("\n请输入选项 (1/2/3/4/5/6/7，回车默认1): ").strip()
    except:
        choice = "1"

    if not choice:
        choice = "1"

    if choice == "7":
        show_weekly_records()
    elif choice == "6":
        show_history_list()
    elif choice == "5":
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
