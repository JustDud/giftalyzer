import asyncio
import pandas as pd
from mongo import nfts_collection
from mongo import collections_collection


async def download_all_nfts_to_csv(output_path="all_nfts.csv"):
    """Download all NFTs from the MongoDB collection and save to a CSV file."""
    nfts = [doc async for doc in nfts_collection.find()]
    df = pd.DataFrame(nfts)
    df.to_csv(output_path, index=False)
    print(f"✅ Exported {len(nfts)} NFTs to {output_path}")


async def download_all_collections_to_csv(output_path="all_collections.csv"):
    """Download all NFTs from the MongoDB collection and save to a CSV file."""
    collections = [doc async for doc in collections_collection.find()]
    df = pd.DataFrame(collections)
    df.to_csv(output_path, index=False)
    print(f"✅ Exported {len(collections)} NFTs to {output_path}")


if __name__ == "__main__":
    asyncio.gather(
        download_all_collections_to_csv(),
        download_all_nfts_to_csv()
    )
