"""前進模擬每日推進 worker。

用法：python -m api.workers.paper_worker
"""
from datetime import date

from api.services import simulation_service, signal_service


def main():
    """推進所有執行中的 paper 模擬到今日。"""
    print("前進 paper trading 模擬...")

    today = date.today()
    sims = simulation_service.list_all()

    for sim in sims:
        if sim.config.kind != "paper" or sim.status == "draft":
            continue

        if sim.state.cursor_date >= today:
            print(f"  {sim.id}: {sim.name} — 已是最新")
            continue

        print(f"  推進 {sim.id}: {sim.name}")
        try:
            # 收集所有候選股票的價格資料
            price_cache = {}
            for cand in sim.config.candidates:
                try:
                    prices = signal_service.get_price_history(cand.code, days=365)
                    price_cache[cand.code] = {
                        p.date: {"open": p.open, "close": p.close} for p in prices
                    }
                except Exception:
                    pass

            simulation_service.advance_paper(sim.id, today, signal_service, price_cache)
            print(f"    ✓ 完成：cursor_date={sim.state.cursor_date}")

        except Exception as e:
            print(f"    ✗ 失敗：{e}")


if __name__ == "__main__":
    main()
