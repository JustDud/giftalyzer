from data_collection.marketapp import data_scraper
from analyser.price_analyser import estimate_ton_price, convert_ton_to_usd
from mongo import export_all_nft_prices_to_csv
import asyncio
from data_collection.tonnel.tonnel_parser import fetch_all_gifts_from_tonnel


async def main():
    data = await fetch_all_gifts_from_tonnel()
    print(data)
    # data_update_requested = False
    #
    # # migrate_collection_names()
    # # delete_specific_collections()
    # if data_update_requested:
    #     data_scraper.scrape_and_update_db()

    #test_estimate_price()

    # Export all NFT prices to CSV
    # export_all_nft_prices_to_csv(estimate_ton_price, convert_ton_to_usd)


if __name__ == "__main__":
    main()
