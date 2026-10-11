from dataclasses import dataclass


@dataclass(frozen=True)
class StockMeta:
    code: str
    name: str
    base_price: float
    sector: str = "其他"


STOCKS: tuple[StockMeta, ...] = (
    StockMeta("600519", "贵州茅台", 1263.00, "白酒"),
    StockMeta("000858", "五粮液", 128.00, "白酒"),
    StockMeta("000568", "泸州老窖", 140.00, "白酒"),
    StockMeta("000001", "平安银行", 11.60, "银行"),
    StockMeta("600036", "招商银行", 38.80, "银行"),
    StockMeta("601398", "工商银行", 6.20, "银行"),
    StockMeta("601318", "中国平安", 52.80, "保险"),
    StockMeta("601628", "中国人寿", 40.00, "保险"),
    StockMeta("300750", "宁德时代", 298.00, "新能源"),
    StockMeta("002594", "比亚迪", 298.00, "新能源"),
    StockMeta("601012", "隆基绿能", 16.80, "新能源"),
    StockMeta("600276", "恒瑞医药", 48.20, "医药"),
    StockMeta("300760", "迈瑞医疗", 250.00, "医药"),
    StockMeta("000333", "美的集团", 72.00, "家电"),
    StockMeta("000651", "格力电器", 40.00, "家电"),
    StockMeta("601899", "紫金矿业", 18.50, "有色"),
    StockMeta("600111", "北方稀土", 30.00, "有色"),
    StockMeta("688981", "中芯国际", 86.00, "半导体"),
    StockMeta("002371", "北方华创", 300.00, "半导体"),
    StockMeta("600887", "伊利股份", 28.00, "食品"),
    StockMeta("603288", "海天味业", 40.00, "食品"),
    StockMeta("600030", "中信证券", 28.00, "证券"),
    StockMeta("300059", "东方财富", 20.00, "证券"),
    StockMeta("600048", "保利发展", 8.00, "地产"),
    StockMeta("000002", "万科A", 7.00, "地产"),
    StockMeta("600900", "长江电力", 28.00, "电力"),
    StockMeta("601985", "中国核电", 9.00, "电力"),
    StockMeta("601633", "长城汽车", 25.00, "汽车"),
    StockMeta("600941", "中国移动", 100.00, "通信"),
    StockMeta("000063", "中兴通讯", 30.00, "通信"),
)

BY_CODE: dict[str, StockMeta] = {item.code: item for item in STOCKS}


def search_stocks(query: str, limit: int = 8) -> list[StockMeta]:
    keyword = query.strip()
    if not keyword:
        return []
    code_hits = [item for item in STOCKS if item.code.startswith(keyword)]
    name_hits = [item for item in STOCKS if keyword in item.name and item not in code_hits]
    return (code_hits + name_hits)[:limit]
