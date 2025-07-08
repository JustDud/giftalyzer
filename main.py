from data_collection.marketapp import data_scraper
from analyser.price_analyser import estimate_ton_price, convert_ton_to_usd
from mongo import export_all_nft_prices_to_csv, migrate_collection_names, delete_specific_collections


def main():
    data_update_requested = False

    # migrate_collection_names()
    # delete_specific_collections()
    if data_update_requested:
        data_scraper.scrape_and_update_db()

    # test_estimate_price()

    # Export all NFT prices to CSV
    # export_all_nft_prices_to_csv(estimate_ton_price, convert_ton_to_usd)




def test_estimate_price():
    nft_id = "EQAXJEh1sqt4NnAiC177t5d9xxjdm974hazlSSwOY12kBq95"
    collection_address = "EQA3-i1IUFjWyDhaIoCGdYUB4nt2IYaT3T-95CHPrSvV3AfX"

    estimated_price = estimate_ton_price(nft_id)
    usd = convert_ton_to_usd(estimated_price)

    print("Estimated TON Price:", estimated_price)
    print("USD: ", usd)
    assert isinstance(estimated_price, float)
    assert estimated_price > 0


if __name__ == "__main__":
    main()
