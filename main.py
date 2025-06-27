import price_analyser
from data_collection.marketapp import data_scraper
from price_analyser import estimate_ton_price


def main():
    data_update_requested = True

    if data_update_requested:
        data_scraper.scrape_and_update_db()

    test_estimate_price()


def test_estimate_price():
    nft_id = "EQDSJQX0Jd04L3KmDS--oFzaX1Urqz5LPT40wdEdGcV3_HeD"
    collection_address = "EQA3-i1IUFjWyDhaIoCGdYUB4nt2IYaT3T-95CHPrSvV3AfX"

    estimated_price = estimate_ton_price(nft_id)

    print("Estimated TON Price:", estimated_price)
    assert isinstance(estimated_price, float)
    assert estimated_price > 0


if __name__ == "__main__":
    main()
