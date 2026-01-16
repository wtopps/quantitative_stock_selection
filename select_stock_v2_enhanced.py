#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股四日形态选股脚本 v2.1 - 增强版
策略：涨停启动 → 放量洗盘 → 回调确认 → 缩量买点（4天连续形态）

v2.1 新增功能：
1. 数据缓存机制：缓存历史K线数据，大幅提升运行速度
2. 游资追踪分析：整合龙虎榜数据，识别游资介入情况
3. 回测验证功能：追踪形态后续表现，验证策略有效性

核心策略：
Day1 (涨停启动): 涨幅>=9.8%，记录基础量V1
Day2 (放量洗盘): 成交量>1.2*V1，涨幅<3%（假阴真阳）
Day3 (回调确认): 涨幅在-5%~0%之间，成交量<1.5*Day2量
Day4 (缩量买点): 成交量<=0.55*V1，涨幅在-3%~3%之间（买入信号）
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
import hashlib
warnings.filterwarnings('ignore')

# ============================================================
# 目录配置
# ============================================================
HISTORY_DIR = Path(__file__).parent / "selection_history"
HISTORY_FILE = HISTORY_DIR / "history_index.json"
WEEKLY_DIR = HISTORY_DIR / "weekly"
HOT_MONEY_CACHE_DIR = Path(__file__).parent / "hot_money_cache"
KLINE_CACHE_DIR = Path(__file__).parent / "kline_cache"  # v2.1新增：K线数据缓存

# 创建必要的目录
HISTORY_DIR.mkdir(parents=True, exist_ok=True)
WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
HOT_MONEY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
KLINE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 缓存配置（v2.1新增）
# ============================================================
CACHE_CONFIG = {
    "kline_expire_hours": 24,  # K线数据缓存24小时
    "enable_cache": True,  # 是否启用缓存
    "cache_version": "v1",  # 缓存版本号
}

# ============================================================
# 游资追踪配置
# ============================================================
KNOWN_HOT_MONEY_DESKS = {
    # 一线游资
    "东方财富证券股份有限公司拉萨团结路第二证券营业部": {"tier": 1, "style": "短线", "success_rate": 0.75},
    "华泰证券股份有限公司深圳益田路荣超商务中心证券营业部": {"tier": 1, "style": "中线", "success_rate": 0.72},
    "国泰君安证券股份有限公司成都北一环路证券营业部": {"tier": 1, "style": "短线", "success_rate": 0.70},
    "中国银河证券股份有限公司绍兴证券营业部": {"tier": 1, "style": "短线", "success_rate": 0.68},
    "招商证券股份有限公司深圳蛇口工业七路证券营业部": {"tier": 1, "style": "波段", "success_rate": 0.71},
    # 二线游资
    "中信证券股份有限公司杭州延安路证券营业部": {"tier": 2, "style": "中线", "success_rate": 0.65},
    "广发证券股份有限公司佛山季华六路证券营业部": {"tier": 2, "style": "短线", "success_rate": 0.63},
    "国信证券股份有限公司深圳泰然九路证券营业部": {"tier": 2, "style": "短线", "success_rate": 0.62},
    "申万宏源证券有限公司上海东川路证券营业部": {"tier": 2, "style": "波段", "success_rate": 0.64},
    "东方财富证券股份有限公司拉萨东环路第二证券营业部": {"tier": 2, "style": "短线", "success_rate": 0.66},
    # 机构席位
    "机构专用": {"tier": 0, "style": "机构", "success_rate": 0.60},
    "沪股通专用": {"tier": 0, "style": "北向", "success_rate": 0.58},
    "深股通专用": {"tier": 0, "style": "北向", "success_rate": 0.58},
}

HOT_MONEY_CONFIG = {
    "lookback_days": 30,
    "min_appearances": 2,
    "min_net_buy": 5000000,
    "continuity_days": 3,
    "weight_in_composite": 0.15,
}

# ============================================================
# 月份主题配置
# ============================================================
MONTHLY_THEMES = {
    1: {"name": "消费预期", "logic": "春节效应，资金围绕吃喝玩乐炒作"},
    2: {"name": "农业预期", "logic": "中央一号文件落地，春耕板块易拉升"},
    3: {"name": "两会预期", "logic": "大会定调全年方向，政策预期板块易爆炒"},
    4: {"name": "年报行情", "logic": "年报季，个股易爆雷，建议多看少动", "warning": "⚠️ 4月年报季，建议谨慎操作！"},
    5: {"name": "电力预期", "logic": "天气升温，用电负荷飙升，电力板块易动作"},
    6: {"name": "中报预期", "logic": "五穷六绝七翻身，业绩预增方向提前炒作"},
    7: {"name": "电力与水利", "logic": "高温限电+干旱洪涝，水利管网板块炒作"},
    8: {"name": "科技", "logic": "华为苹果新品发布集中，科技股易起飞"},
    9: {"name": "消费旅游", "logic": "国庆黄金周提前布局，旅游酒店板块"},
    10: {"name": "电商物流", "logic": "双11预热，物流快递、线上零售火爆"},
    11: {"name": "供热", "logic": "入冬供暖需求暴增，煤炭燃气板块拉升"},
    12: {"name": "妖股跨年", "logic": "跨年行情，妖股和低价股资金扎堆炒作"},
}


class CacheManager:
    """
    缓存管理器（v2.1新增）
    负责K线数据的缓存读写，大幅提升重复运行速度
    """

    def __init__(self):
        self.cache_dir = KLINE_CACHE_DIR
        self.expire_hours = CACHE_CONFIG['kline_expire_hours']
        self.enabled = CACHE_CONFIG['enable_cache']
        self.version = CACHE_CONFIG['cache_version']

    def _get_cache_key(self, stock_code, days):
        """生成缓存键"""
        key_str = f"{stock_code}_{days}_{self.version}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cache_path(self, cache_key):
        """获取缓存文件路径"""
        # 按日期分目录存储
        today = datetime.now().strftime('%Y%m%d')
        date_dir = self.cache_dir / today
        date_dir.mkdir(exist_ok=True)
        return date_dir / f"{cache_key}.pkl"

    def _is_cache_valid(self, cache_path):
        """检查缓存是否有效"""
        if not cache_path.exists():
            return False

        # 检查文件修改时间
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        now = datetime.now()
        age_hours = (now - mtime).total_seconds() / 3600

        return age_hours < self.expire_hours

    def get(self, stock_code, days):
        """读取缓存"""
        if not self.enabled:
            return None

        try:
            cache_key = self._get_cache_key(stock_code, days)
            cache_path = self._get_cache_path(cache_key)

            if self._is_cache_valid(cache_path):
                df = pd.read_pickle(cache_path)
                return df
        except Exception as e:
            pass

        return None

    def set(self, stock_code, days, data):
        """写入缓存"""
        if not self.enabled or data is None:
            return

        try:
            cache_key = self._get_cache_key(stock_code, days)
            cache_path = self._get_cache_path(cache_key)

            # 保存为pickle格式（速度快）
            data.to_pickle(cache_path)
        except Exception as e:
            pass

    def clear_old_caches(self):
        """清理过期缓存"""
        try:
            for date_dir in self.cache_dir.iterdir():
                if not date_dir.is_dir():
                    continue

                # 删除3天前的缓存目录
                try:
                    date_str = date_dir.name
                    cache_date = datetime.strptime(date_str, '%Y%m%d')
                    age_days = (datetime.now() - cache_date).days

                    if age_days > 3:
                        import shutil
                        shutil.rmtree(date_dir)
                        print(f"   已清理过期缓存: {date_str}")
                except:
                    pass
        except Exception as e:
            pass


class StockScreener:
    """股票筛选器 - v2.1 增强版"""

    def __init__(self, target_sector=None):
        self.today = datetime.now().strftime('%Y%m%d')
        self.current_month = datetime.now().month
        self.theme = MONTHLY_THEMES.get(self.current_month, {})
        self.batch_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.selection_date = datetime.now().strftime('%Y-%m-%d')
        self.is_monday = datetime.now().weekday() == 0
        self.lhb_cache = None  # 龙虎榜数据缓存

        # v2.1新增：缓存管理器
        self.cache_manager = CacheManager()

        # 统计信息
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'api_calls': 0,
        }

    def get_historical_data(self, stock_code, days=30):
        """
        获取个股历史K线数据（v2.1增强：支持缓存）
        """
        # 先尝试从缓存读取
        cached_data = self.cache_manager.get(stock_code, days)
        if cached_data is not None:
            self.stats['cache_hits'] += 1
            return cached_data

        self.stats['cache_misses'] += 1

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

            self.stats['api_calls'] += 1

            # 写入缓存
            if df is not None and not df.empty:
                self.cache_manager.set(stock_code, days, df)

            return df
        except Exception as e:
            return None

    # ========== 游资追踪功能（从v9.1完整移植）==========

    def fetch_lhb_data(self, stock_code, lookback_days=30):
        """获取个股龙虎榜数据"""
        try:
            # 构建缓存文件路径
            cache_file = HOT_MONEY_CACHE_DIR / f"lhb_{stock_code}_{datetime.now().strftime('%Y%m%d')}.json"

            # 检查缓存
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

            try:
                # 使用全局缓存，避免重复获取
                if self.lhb_cache is None:
                    try:
                        self.lhb_cache = ak.stock_lhb_detail_em(
                            start_date=start_date.strftime('%Y%m%d'),
                            end_date=end_date.strftime('%Y%m%d')
                        )
                        if self.lhb_cache is not None and not self.lhb_cache.empty:
                            pass
                        else:
                            self.lhb_cache = pd.DataFrame()
                    except Exception as e:
                        self.lhb_cache = pd.DataFrame()

                # 从缓存中过滤出当前股票的记录
                df_lhb = None
                if self.lhb_cache is not None and not self.lhb_cache.empty:
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
                        for i in range(1, 6):
                            buy_desk = row.get(f'买{i}营业部', '')
                            sell_desk = row.get(f'卖{i}营业部', '')
                            buy_amount_val = row.get(f'买{i}金额', 0)
                            sell_amount_val = row.get(f'卖{i}金额', 0)

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

                    # 转换为普通dict
                    result['buy_desks'] = dict(result['buy_desks'])
                    result['sell_desks'] = dict(result['sell_desks'])

            except Exception as e:
                pass

            # 保存缓存
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
            except:
                pass

            return result

        except Exception as e:
            return {
                'appearances': 0,
                'records': [],
                'buy_desks': {},
                'sell_desks': {},
                'net_buy': 0
            }

    def calculate_hot_money_strength(self, lhb_data, stock_code):
        """计算游资强度评分"""
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

                    if tier == 1:
                        hot_money_involvement += 10
                        result['hot_money_desks'].append({
                            'name': desk,
                            'tier': '一线',
                            'style': desk_info['style'],
                            'amount': amount,
                            'success_rate': desk_info['success_rate']
                        })
                    elif tier == 2:
                        hot_money_involvement += 6
                        result['hot_money_desks'].append({
                            'name': desk,
                            'tier': '二线',
                            'style': desk_info['style'],
                            'amount': amount,
                            'success_rate': desk_info['success_rate']
                        })
                    else:
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
            if net_buy >= 50000000:
                result['net_buy_score'] = 25
            elif net_buy >= 30000000:
                result['net_buy_score'] = 20
            elif net_buy >= 10000000:
                result['net_buy_score'] = 15
            elif net_buy >= 5000000:
                result['net_buy_score'] = 10
            elif net_buy > 0:
                result['net_buy_score'] = 5
            else:
                result['net_buy_score'] = 0
                result['risk_level'] = '高'

            # 4. 持续性评分（0-15分）
            records = lhb_data['records']
            if len(records) >= 2:
                dates = sorted([r['date'] for r in records if r['date']], reverse=True)
                continuous_days = 1

                for i in range(len(dates) - 1):
                    try:
                        date1 = datetime.strptime(dates[i], '%Y-%m-%d')
                        date2 = datetime.strptime(dates[i + 1], '%Y-%m-%d')
                        diff = (date1 - date2).days

                        if diff <= 3:
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
        """评估买入时机"""
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
                result['stage'] = '建仓期'
                result['timing_score'] = 85
                result['recommendation'] = '积极关注'
                result['reason'] = f'游资低位建仓，价格位于底部区域({price_position*100:.1f}%)'

            elif 0.3 <= price_position < 0.6 and net_buy > HOT_MONEY_CONFIG['min_net_buy']:
                result['stage'] = '加仓期'
                result['timing_score'] = 75
                result['recommendation'] = '适合跟进'
                result['reason'] = f'游资持续加仓，价格温和上涨({price_position*100:.1f}%)'

            elif 0.6 <= price_position < 0.85 and avg_change > 3:
                result['stage'] = '拉升期'
                result['timing_score'] = 60
                result['recommendation'] = '短线参与'
                result['reason'] = f'游资拉升中，追高风险较大({price_position*100:.1f}%)'

            elif price_position >= 0.85 or net_buy < 0:
                result['stage'] = '出货期'
                result['timing_score'] = 20
                result['recommendation'] = '回避'
                result['reason'] = f'游资可能出货，风险较高({price_position*100:.1f}%位置)'

            else:
                result['stage'] = '观望'
                result['timing_score'] = 40
                result['recommendation'] = '观望'
                result['reason'] = '游资意图不明确，建议观望'

            return result

        except Exception as e:
            return {
                'stage': '未知',
                'timing_score': 0,
                'recommendation': '观望',
                'reason': '数据异常'
            }

    def analyze_hot_money_for_stock(self, stock_code, current_price, recent_high, recent_low):
        """综合分析个股游资情况"""
        try:
            # 1. 获取龙虎榜数据
            lhb_data = self.fetch_lhb_data(stock_code, HOT_MONEY_CONFIG['lookback_days'])

            # 2. 计算游资强度
            strength = self.calculate_hot_money_strength(lhb_data, stock_code)

            # 3. 评估买入时机
            timing = self.assess_buy_timing(lhb_data, current_price, recent_high, recent_low)

            # 综合结果
            analysis = {
                'stock_code': stock_code,
                'lhb_appearances': lhb_data['appearances'],
                'net_buy_amount': lhb_data['net_buy'],
                'strength_score': strength['total_score'],
                'strength_detail': strength,
                'timing_score': timing['timing_score'],
                'timing_detail': timing,
                'has_hot_money': lhb_data['appearances'] >= HOT_MONEY_CONFIG['min_appearances'],
                'is_active': lhb_data['appearances'] >= HOT_MONEY_CONFIG['min_appearances'] and lhb_data['net_buy'] > 0,
            }

            return analysis

        except Exception as e:
            return {
                'stock_code': stock_code,
                'lhb_appearances': 0,
                'net_buy_amount': 0,
                'strength_score': 0,
                'timing_score': 0,
                'has_hot_money': False,
                'is_active': False,
                'strength_detail': {},
                'timing_detail': {},
            }

    # ========== 回测功能（v2.1新增）==========

    def backtest_pattern(self, stock_code, pattern_start_date, buy_date):
        """
        回测四日形态的后续表现

        参数：
            stock_code: 股票代码
            pattern_start_date: 形态起始日期（Day1）
            buy_date: 买入日期（Day4）

        返回：
            回测结果字典
        """
        try:
            # 获取买入日期之后的数据
            buy_dt = datetime.strptime(buy_date, '%Y-%m-%d')
            end_dt = datetime.now()

            # 如果买入日期是今天或未来，无法回测
            if buy_dt.date() >= end_dt.date():
                return {
                    'can_backtest': False,
                    'reason': '买入日期是今天或未来，暂无后续数据'
                }

            # 获取历史数据
            hist_data = self.get_historical_data(stock_code, days=60)

            if hist_data is None or hist_data.empty:
                return {
                    'can_backtest': False,
                    'reason': '无法获取历史数据'
                }

            # 转换日期格式
            hist_data['日期'] = pd.to_datetime(hist_data['日期'])

            # 找到买入日期的索引
            buy_data = hist_data[hist_data['日期'] == buy_dt]

            if buy_data.empty:
                return {
                    'can_backtest': False,
                    'reason': '未找到买入日期数据'
                }

            buy_idx = buy_data.index[0]
            buy_price = float(buy_data.iloc[0]['收盘'])

            # 计算后续表现
            result = {
                'can_backtest': True,
                'buy_price': buy_price,
                'buy_date': buy_date,
                'next_day_change': None,
                'day3_change': None,
                'day5_change': None,
                'max_gain': 0,
                'max_loss': 0,
                'current_change': None,
                'best_sell_day': None,
                'best_sell_price': None,
                'days_tracked': 0,
            }

            # 追踪后续最多10个交易日的表现
            max_track_days = min(10, len(hist_data) - buy_idx - 1)

            if max_track_days <= 0:
                return result

            result['days_tracked'] = max_track_days

            max_gain_price = buy_price
            max_gain_day = 0
            max_loss_price = buy_price

            for i in range(1, max_track_days + 1):
                if buy_idx + i >= len(hist_data):
                    break

                future_price = float(hist_data.iloc[buy_idx + i]['收盘'])
                change = (future_price - buy_price) / buy_price * 100

                # 记录各天涨幅
                if i == 1:
                    result['next_day_change'] = change
                elif i == 3:
                    result['day3_change'] = change
                elif i == 5:
                    result['day5_change'] = change

                # 追踪最大涨幅
                if future_price > max_gain_price:
                    max_gain_price = future_price
                    max_gain_day = i

                # 追踪最大回撤
                if future_price < max_loss_price:
                    max_loss_price = future_price

            # 计算最大涨幅和最大回撤
            result['max_gain'] = (max_gain_price - buy_price) / buy_price * 100
            result['max_loss'] = (max_loss_price - buy_price) / buy_price * 100
            result['best_sell_day'] = max_gain_day
            result['best_sell_price'] = max_gain_price

            # 如果有当前价格，计算当前涨幅
            if buy_idx + max_track_days < len(hist_data):
                current_price = float(hist_data.iloc[buy_idx + max_track_days]['收盘'])
                result['current_change'] = (current_price - buy_price) / buy_price * 100
            elif max_track_days > 0:
                current_price = float(hist_data.iloc[buy_idx + max_track_days]['收盘'])
                result['current_change'] = (current_price - buy_price) / buy_price * 100

            return result

        except Exception as e:
            return {
                'can_backtest': False,
                'reason': f'回测异常: {str(e)[:50]}'
            }

    # ========== 核心选股逻辑 ==========

    def identify_4day_pattern(self, df_all):
        """识别四日形态"""
        print("\n" + "=" * 70)
        print("【开始四日形态识别】v2.1 增强版")
        print("=" * 70)
        print("\n⏳ 第一步：筛选上证A股（60开头）...")

        # 清理过期缓存
        print("\n⏳ 清理过期缓存...")
        self.cache_manager.clear_old_caches()

        try:
            realtime_df = ak.stock_zh_a_spot_em()
        except Exception as e:
            print(f"❌ 获取实时数据失败: {e}")
            return pd.DataFrame()

        shanghai_stocks = realtime_df[realtime_df['代码'].str.startswith('60')].copy()
        shanghai_stocks = shanghai_stocks[~shanghai_stocks['名称'].str.contains('ST|退', na=False)]

        print(f"✅ 共获取 {len(shanghai_stocks)} 只上证A股（已排除ST股）")

        if shanghai_stocks.empty:
            print("❌ 未找到符合条件的上证A股")
            return pd.DataFrame()

        print(f"\n⏳ 第二步：逐个分析每只股票的历史K线数据...")
        print(f"   💡 启用缓存机制，大幅提升分析速度")

        qualified_stocks = []
        total_stocks = len(shanghai_stocks)
        processed = 0
        found_pattern_count = 0

        max_workers = min(10, total_stocks)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_code = {
                executor.submit(self._analyze_single_stock_pattern, row): row
                for idx, row in shanghai_stocks.iterrows()
            }

            for future in as_completed(future_to_code):
                row = future_to_code[future]
                processed += 1

                try:
                    pattern_result = future.result()

                    if pattern_result is not None:
                        qualified_stocks.append(pattern_result)
                        found_pattern_count += 1

                except Exception as e:
                    pass

                if processed % 50 == 0 or processed == total_stocks:
                    print(f"   ⏳ 已分析 {processed}/{total_stocks} ({processed*100//total_stocks}%) | "
                          f"找到形态: {found_pattern_count} 只 | "
                          f"缓存命中: {self.stats['cache_hits']} | "
                          f"缓存未命中: {self.stats['cache_misses']}")

        print(f"\n✅ 分析完成！共发现 {found_pattern_count} 只符合四日形态的股票")
        print(f"   📊 缓存统计: 命中率 {self.stats['cache_hits']/(self.stats['cache_hits']+self.stats['cache_misses'])*100:.1f}% "
              f"({self.stats['cache_hits']}/{self.stats['cache_hits']+self.stats['cache_misses']})")

        if not qualified_stocks:
            return pd.DataFrame()

        df_result = pd.DataFrame(qualified_stocks)

        # 过滤掉形态周期早于10天以上的股票
        print(f"\n⏳ 第三步：过滤时效性...")
        original_count = len(df_result)
        current_date = datetime.now()
        df_result['pattern_start_date_dt'] = pd.to_datetime(df_result['pattern_start_date'])
        df_result['days_since_pattern'] = (current_date - df_result['pattern_start_date_dt']).dt.days

        # 只保留10天以内的形态
        df_result = df_result[df_result['days_since_pattern'] <= 10].copy()
        filtered_count = original_count - len(df_result)

        if filtered_count > 0:
            print(f"   ✅ 过滤掉 {filtered_count} 只超过10天的旧形态，保留 {len(df_result)} 只")
        else:
            print(f"   ✅ 所有形态均在10天以内，无需过滤")

        # 删除临时列
        df_result = df_result.drop(columns=['pattern_start_date_dt', 'days_since_pattern'])

        df_result = df_result.sort_values('pattern_start_date', ascending=False)

        return df_result

    def _analyze_single_stock_pattern(self, stock_row):
        """分析单只股票是否符合四日形态"""
        stock_code = stock_row['代码']
        stock_name = stock_row['名称']

        try:
            hist_data = self.get_historical_data(stock_code, days=30)

            if hist_data is None or len(hist_data) < 10:
                return None

            hist_data = hist_data.sort_values('日期')
            hist_data = hist_data.reset_index(drop=True)

            if '涨跌幅' not in hist_data.columns:
                hist_data['涨跌幅'] = hist_data['收盘'].pct_change() * 100

            for i in range(len(hist_data) - 4, -1, -1):
                if i + 4 > len(hist_data):
                    continue

                day1 = hist_data.iloc[i]
                day2 = hist_data.iloc[i + 1]
                day3 = hist_data.iloc[i + 2]
                day4 = hist_data.iloc[i + 3]

                is_pattern, pattern_info = self._check_4day_pattern(day1, day2, day3, day4)

                if is_pattern:
                    result = {
                        '代码': stock_code,
                        '名称': stock_name,
                        'pattern_start_date': pd.to_datetime(day1['日期']).strftime('%Y-%m-%d'),
                        'buy_date': pd.to_datetime(day4['日期']).strftime('%Y-%m-%d'),

                        'day1_date': pd.to_datetime(day1['日期']).strftime('%Y-%m-%d'),
                        'day1_close': float(day1['收盘']),
                        'day1_vol': float(day1['成交量']),
                        'day1_pct_chg': float(day1.get('涨跌幅', 0)),

                        'day2_date': pd.to_datetime(day2['日期']).strftime('%Y-%m-%d'),
                        'day2_close': float(day2['收盘']),
                        'day2_vol': float(day2['成交量']),
                        'day2_pct_chg': float(day2.get('涨跌幅', 0)),

                        'day3_date': pd.to_datetime(day3['日期']).strftime('%Y-%m-%d'),
                        'day3_close': float(day3['收盘']),
                        'day3_vol': float(day3['成交量']),
                        'day3_pct_chg': float(day3.get('涨跌幅', 0)),

                        'day4_date': pd.to_datetime(day4['日期']).strftime('%Y-%m-%d'),
                        'day4_close': float(day4['收盘']),
                        'day4_vol': float(day4['成交量']),
                        'day4_pct_chg': float(day4.get('涨跌幅', 0)),

                        'vol_ratio_day2': pattern_info['vol_ratio_day2'],
                        'vol_ratio_day3': pattern_info['vol_ratio_day3'],
                        'vol_ratio_day4': pattern_info['vol_ratio_day4'],

                        '最新价': float(day4['收盘']),
                        '涨跌幅': float(day4.get('涨跌幅', 0)),
                        '量比': pattern_info['vol_ratio_day4'] / 0.55,
                        '换手率': stock_row.get('换手率', 0),
                        '流通市值': stock_row.get('流通市值', 0),
                        '成交额': float(day4.get('成交额', 0)),
                    }

                    return result

            return None

        except Exception as e:
            return None

    def _check_4day_pattern(self, day1, day2, day3, day4):
        """检查四天数据是否符合形态要求"""
        try:
            v1 = float(day1['成交量'])
            v2 = float(day2['成交量'])
            v3 = float(day3['成交量'])
            v4 = float(day4['成交量'])

            pct1 = float(day1.get('涨跌幅', 0))
            pct2 = float(day2.get('涨跌幅', 0))
            pct3 = float(day3.get('涨跌幅', 0))
            pct4 = float(day4.get('涨跌幅', 0))

            # Day1: 涨停启动
            if pct1 < 9.8:
                return False, {}

            # Day2: 放量洗盘
            if v2 <= v1 * 1.2:
                return False, {}
            if pct2 >= 3.0:
                return False, {}

            # Day3: 回调确认
            if pct3 >= 0 or pct3 <= -5.0:
                return False, {}
            if v3 >= v2 * 1.5:
                return False, {}

            # Day4: 缩量买点
            if v4 > v1 * 0.55:
                return False, {}
            if pct4 < -3.0 or pct4 > 3.0:
                return False, {}

            pattern_info = {
                'vol_ratio_day2': v2 / v1,
                'vol_ratio_day3': v3 / v2,
                'vol_ratio_day4': v4 / v1,
            }

            return True, pattern_info

        except Exception as e:
            return False, {}

    def add_enhanced_analysis(self, df):
        """
        添加增强分析（v2.1：整合游资+回测）
        """
        if df.empty:
            return df

        print("\n⏳ 第四步：为筛选出的股票添加增强分析...")
        print("   📊 分析内容：技术指标 + 游资追踪 + 回测验证")

        qualified_stocks = []
        processed = 0
        total = len(df)

        for idx, row in df.iterrows():
            stock_code = row['代码']
            processed += 1

            if processed % 3 == 0 or processed == total:
                print(f"   ⏳ 已分析 {processed}/{total}...")

            # 1. 技术分析
            hist_data = self.get_historical_data(stock_code, days=90)

            if hist_data is None or len(hist_data) < 60:
                row_copy = row.copy()
                row_copy['流通市值_亿'] = row.get('流通市值', 0) / 1e8
                row_copy['MA5'] = row['day4_close']
                row_copy['MA10'] = row['day4_close']
                row_copy['MA20'] = row['day4_close']
                row_copy['MA60'] = row['day4_close']
                row_copy['均线排列'] = '未知'
                row_copy['综合评分'] = 50
                row_copy['综合评级'] = 'B(一般)'

                # 游资分析（使用默认值）
                row_copy['游资评分'] = 0
                row_copy['龙虎榜次数'] = 0
                row_copy['游资阶段'] = '未知'
                row_copy['游资建议'] = '观望'

                # 回测（无法进行）
                row_copy['可回测'] = False
                row_copy['次日涨幅'] = None

                qualified_stocks.append(row_copy)
                continue

            # 计算均线
            hist_data['MA5'] = hist_data['收盘'].rolling(window=5).mean()
            hist_data['MA10'] = hist_data['收盘'].rolling(window=10).mean()
            hist_data['MA20'] = hist_data['收盘'].rolling(window=20).mean()
            hist_data['MA60'] = hist_data['收盘'].rolling(window=60).mean()

            latest = hist_data.iloc[-1]

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

            # 2. 游资分析
            recent_high = hist_data['最高'].tail(60).max() if len(hist_data) >= 60 else hist_data['最高'].max()
            recent_low = hist_data['最低'].tail(60).min() if len(hist_data) >= 60 else hist_data['最低'].min()

            hot_money_analysis = self.analyze_hot_money_for_stock(
                stock_code, row['day4_close'], recent_high, recent_low
            )

            # 3. 回测分析
            backtest_result = self.backtest_pattern(
                stock_code, row['pattern_start_date'], row['buy_date']
            )

            # 4. 综合评分
            score = 50

            # Day2放量程度加分
            vol_ratio_day2 = row['vol_ratio_day2']
            if vol_ratio_day2 >= 2.0:
                score += 15
            elif vol_ratio_day2 >= 1.5:
                score += 10
            elif vol_ratio_day2 >= 1.2:
                score += 5

            # Day4缩量程度加分
            vol_ratio_day4 = row['vol_ratio_day4']
            if vol_ratio_day4 <= 0.3:
                score += 15
            elif vol_ratio_day4 <= 0.4:
                score += 10
            elif vol_ratio_day4 <= 0.55:
                score += 5

            # 均线排列加分
            score += ma_score

            # 涨停强度加分
            if row['day1_pct_chg'] >= 9.9:
                score += 10
            elif row['day1_pct_chg'] >= 9.8:
                score += 5

            # 游资加分
            if hot_money_analysis['is_active']:
                score += 10
            elif hot_money_analysis['has_hot_money']:
                score += 5

            # 回测加分（如果可以回测且表现好）
            if backtest_result.get('can_backtest') and backtest_result.get('next_day_change') is not None:
                if backtest_result['next_day_change'] > 5:
                    score += 10
                elif backtest_result['next_day_change'] > 0:
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

            # 游资字段
            row_copy['游资评分'] = hot_money_analysis['strength_score']
            row_copy['龙虎榜次数'] = hot_money_analysis['lhb_appearances']
            row_copy['游资净买入'] = hot_money_analysis['net_buy_amount']
            row_copy['游资阶段'] = hot_money_analysis.get('timing_detail', {}).get('stage', '未知')
            row_copy['游资建议'] = hot_money_analysis.get('timing_detail', {}).get('recommendation', '观望')
            row_copy['游资活跃'] = hot_money_analysis['is_active']

            # 回测字段
            row_copy['可回测'] = backtest_result.get('can_backtest', False)
            if backtest_result.get('can_backtest'):
                row_copy['次日涨幅'] = backtest_result.get('next_day_change')
                row_copy['3日涨幅'] = backtest_result.get('day3_change')
                row_copy['5日涨幅'] = backtest_result.get('day5_change')
                row_copy['最大涨幅'] = backtest_result.get('max_gain')
                row_copy['最大回撤'] = backtest_result.get('max_loss')
                row_copy['最佳卖点'] = backtest_result.get('best_sell_day')
            else:
                row_copy['次日涨幅'] = None
                row_copy['3日涨幅'] = None
                row_copy['5日涨幅'] = None
                row_copy['最大涨幅'] = None
                row_copy['最大回撤'] = None
                row_copy['最佳卖点'] = None

            qualified_stocks.append(row_copy)

        df_result = pd.DataFrame(qualified_stocks)
        df_result = df_result.sort_values('综合评分', ascending=False)

        print(f"\n✅ 增强分析完成")

        # 统计回测信息
        can_backtest = len(df_result[df_result['可回测'] == True])
        if can_backtest > 0:
            backtest_df = df_result[df_result['可回测'] == True]
            avg_next_day = backtest_df['次日涨幅'].mean()
            win_rate = len(backtest_df[backtest_df['次日涨幅'] > 0]) / len(backtest_df) * 100
            print(f"   📊 回测统计: {can_backtest}只可回测 | 次日平均涨幅{avg_next_day:.2f}% | 胜率{win_rate:.1f}%")

        return df_result

    def save_selection_result(self, df):
        """保存选股结果"""
        if df.empty:
            print("\n📝 本次无选股结果，不保存历史记录")
            return None

        selection_data = {
            'batch_id': self.batch_id,
            'selection_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'selection_date': datetime.now().strftime('%Y-%m-%d'),
            'stock_count': len(df),
            'strategy': '四日形态(涨停启动+缩量买点)',
            'stocks': []
        }

        for idx, row in df.iterrows():
            stock_info = {
                'code': row['代码'],
                'name': row['名称'],
                'selection_price': row.get('day4_close', 0),
                'rating': row.get('综合评级', ''),
                'composite_score': row.get('综合评分', 0),
                'pattern_start_date': row.get('pattern_start_date', ''),
                'buy_date': row.get('buy_date', ''),
                'hot_money_active': row.get('游资活跃', False),
            }
            selection_data['stocks'].append(stock_info)

        batch_file = HISTORY_DIR / f"batch_{self.batch_id}.json"
        with open(batch_file, 'w', encoding='utf-8') as f:
            json.dump(selection_data, f, ensure_ascii=False, indent=2)

        print(f"\n📝 选股结果已保存")
        print(f"   批次ID: {self.batch_id}")
        print(f"   保存路径: {batch_file}")

        return self.batch_id

    def print_header(self):
        """打印头部信息"""
        print("=" * 70)
        print("【A股四日形态选股系统 v2.1 - 增强版】")
        print(f"筛选日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔖 批次ID: {self.batch_id}")
        print("🎯 策略: Day1涨停 → Day2放量洗盘 → Day3回调 → Day4缩量买点")
        print("📊 适用: 仅上证A股（60开头）")
        print("🆕 v2.1新功能: 数据缓存 + 游资追踪 + 回测验证")
        print("=" * 70)

    def run(self):
        """执行完整筛选流程"""
        self.print_header()

        print("\n" + "=" * 70)
        print("【开始四日形态筛选】v2.1")
        print("=" * 70)

        # 执行形态识别
        df = self.identify_4day_pattern(None)

        if df.empty:
            print("\n🔴 今日暂无符合四日形态的标的")
            return

        # 添加增强分析
        df = self.add_enhanced_analysis(df)

        # 输出结果
        self.output_result(df)

    def output_result(self, df):
        """输出筛选结果"""
        print("\n" + "=" * 70)
        print("【筛选结果】v2.1 四日形态 + 游资追踪 + 回测验证")
        print("=" * 70)

        if df.empty:
            print("\n🔴 今日暂无符合条件的标的")
            return

        # 保存结果
        self.save_selection_result(df)

        print(f"\n🟢 共筛选出 {len(df)} 只符合四日形态的上证A股")

        # 按评级分类
        aaa_stocks = df[df['综合评级'].str.startswith('AAA')]
        aa_stocks = df[df['综合评级'].str.startswith('AA') & ~df['综合评级'].str.startswith('AAA')]
        a_stocks = df[df['综合评级'].str.startswith('A') & ~df['综合评级'].str.startswith('AA')]
        other_stocks = df[~df['综合评级'].str.startswith('A')]

        # 显示各级标的
        for level, stocks, title in [
            ('AAA', aaa_stocks, '⭐⭐⭐ 【AAA级 - 极强形态】'),
            ('AA', aa_stocks, '⭐⭐ 【AA级 - 强势形态】'),
            ('A', a_stocks, '⭐ 【A级 - 良好形态】'),
            ('other', other_stocks, '📋 【B/C级 - 观察形态】'),
        ]:
            if not stocks.empty:
                print(f"\n{'='*60}")
                print(f"{title}({len(stocks)}只)")
                print(f"{'='*60}")

                for idx, row in stocks.iterrows():
                    if level == 'other' and idx >= stocks.index[5]:
                        break
                    self._print_stock_detail_v2(row, level=level)

                if level == 'other' and len(stocks) > 5:
                    print(f"\n   ... 还有 {len(stocks) - 5} 只")

        # 代码汇总
        print("\n" + "-" * 60)
        print("📋 股票代码汇总:")
        if not aaa_stocks.empty:
            print(f"   ⭐⭐⭐ AAA级: {', '.join(aaa_stocks['代码'].tolist())}")
        if not aa_stocks.empty:
            print(f"   ⭐⭐ AA级: {', '.join(aa_stocks['代码'].tolist())}")
        if not a_stocks.empty:
            print(f"   ⭐ A级: {', '.join(a_stocks['代码'].tolist())}")

        # v2.1新增：回测统计
        can_backtest_df = df[df['可回测'] == True]
        if not can_backtest_df.empty:
            print("\n" + "-" * 60)
            print("📊 【回测统计】v2.1")
            print("-" * 60)

            next_day_changes = can_backtest_df['次日涨幅'].dropna()
            if not next_day_changes.empty:
                avg_next = next_day_changes.mean()
                max_next = next_day_changes.max()
                min_next = next_day_changes.min()
                win_count = len(next_day_changes[next_day_changes > 0])
                win_rate = win_count / len(next_day_changes) * 100

                print(f"   可回测样本: {len(can_backtest_df)} 只")
                print(f"   次日平均涨幅: {avg_next:+.2f}%")
                print(f"   次日最大涨幅: {max_next:+.2f}%")
                print(f"   次日最大跌幅: {min_next:+.2f}%")
                print(f"   次日胜率: {win_rate:.1f}% ({win_count}/{len(next_day_changes)})")

                # 3日和5日统计
                day3_changes = can_backtest_df['3日涨幅'].dropna()
                if not day3_changes.empty:
                    avg_3d = day3_changes.mean()
                    print(f"   3日平均涨幅: {avg_3d:+.2f}%")

                day5_changes = can_backtest_df['5日涨幅'].dropna()
                if not day5_changes.empty:
                    avg_5d = day5_changes.mean()
                    print(f"   5日平均涨幅: {avg_5d:+.2f}%")

                # 最佳卖点统计
                best_sell_days = can_backtest_df['最佳卖点'].dropna()
                if not best_sell_days.empty:
                    avg_best = best_sell_days.mean()
                    print(f"   平均最佳卖点: 第{avg_best:.1f}天")

        # 游资统计
        hot_money_active = len(df[df['游资活跃'] == True])
        if hot_money_active > 0:
            print("\n" + "-" * 60)
            print("💰 【游资统计】v2.1")
            print("-" * 60)
            print(f"   游资活跃: {hot_money_active} 只")

            for stage in ['建仓期', '加仓期']:
                stage_stocks = df[df['游资阶段'] == stage]
                if not stage_stocks.empty:
                    print(f"   {stage}: {len(stage_stocks)} 只")

        print("\n" + "=" * 70)
        print("⚠️  风险提示: 本筛选仅供参考，不构成投资建议")
        print("=" * 70)

    def _print_stock_detail_v2(self, row, level='A'):
        """打印个股详细信息"""
        icons = {'AAA': '🔥', 'AA': '📈', 'A': '📌', 'other': '📋'}
        icon = icons.get(level, '📋')

        print(f"\n  {icon} {row['代码']} | {row['名称']}")
        print(f"     🏆 综合评级: {row['综合评级']} | 评分: {row['综合评分']:.1f}")
        print(f"     📅 形态周期: {row['pattern_start_date']} ~ {row['buy_date']}")
        print(f"     💰 买入价格: {row['day4_close']:.2f}元")

        # 四日数据
        print(f"\n     📊 四日形态:")
        print(f"        Day1: 涨停{row['day1_pct_chg']:.2f}% | 量{row['day1_vol']:.0f}")
        print(f"        Day2: 涨{row['day2_pct_chg']:.2f}% | 量{row['day2_vol']:.0f} (放量{row['vol_ratio_day2']:.2f}倍)")
        print(f"        Day3: 跌{abs(row['day3_pct_chg']):.2f}% | 量{row['day3_vol']:.0f}")
        print(f"        Day4: 涨{row['day4_pct_chg']:.2f}% | 量{row['day4_vol']:.0f} (缩量至{row['vol_ratio_day4']:.2f}倍)")

        # 技术分析
        print(f"\n     📈 技术分析: {row['均线排列']}")

        # v2.1新增：游资信息
        if row['龙虎榜次数'] > 0 or row['游资活跃']:
            net_buy_yi = row['游资净买入'] / 1e8
            active_tag = "🔥活跃" if row['游资活跃'] else ""
            print(f"     💰 游资动向: 上榜{row['龙虎榜次数']}次 | 净买入{net_buy_yi:.2f}亿 {active_tag}")
            print(f"        阶段: {row['游资阶段']} | 建议: {row['游资建议']}")

        # v2.1新增：回测信息
        if row['可回测']:
            print(f"     📊 回测验证:")
            if row['次日涨幅'] is not None:
                status = "✅" if row['次日涨幅'] > 0 else "❌"
                print(f"        次日涨幅: {row['次日涨幅']:+.2f}% {status}")
            if row['最大涨幅'] is not None:
                print(f"        最大涨幅: {row['最大涨幅']:+.2f}% (第{row['最佳卖点']}天)")
            if row['最大回撤'] is not None:
                print(f"        最大回撤: {row['最大回撤']:+.2f}%")


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("【A股四日形态选股系统 v2.1 - 增强版】")
    print("  🎯 核心策略: Day1涨停 → Day2放量 → Day3回调 → Day4缩量")
    print("  📊 适用范围: 仅上证A股（60开头）")
    print("  🆕 v2.1新功能:")
    print("     1️⃣  数据缓存: 大幅提升运行速度")
    print("     2️⃣  游资追踪: 龙虎榜分析+买入时机判断")
    print("     3️⃣  回测验证: 追踪形态后续表现，验证策略有效性")
    print("=" * 70)
    print("\n⏳ 开始执行选股...")

    screener = StockScreener()
    screener.run()


if __name__ == "__main__":
    main()
