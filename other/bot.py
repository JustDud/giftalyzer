# import requests
#
# url = "https://api.getgems.io/graphql"
# headers = {"Content-Type": "application/json"}
#
# query = """
# query GetNFTs($input: FilterInput!, $first: Int!) {
#   nftItems(filter: $input, first: $first) {
#     items {
#       name
#       address
#       sale {
#         __typename
#         ... on NftSaleFixPrice {
#           fullPrice
#         }
#         ... on NftSaleFixPriceDisintar {
#           fullPrice
#         }
#       }
#     }
#   }
# }
# """
#
# variables = {
#     "input": {
#         "collectionAddress": "EQB5I27CQfV-bGKwD_rInFtJ5RxFt5d81jKqkaM9TFIp9uQl",  # замените на нужную коллекцию
#         "onSale": True
#     },
#     "first": 10
# }
#
# response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
# data = response.json()
#
# if "errors" in data:
#     print("GraphQL error:", data["errors"])
# else:
#     for nft in data['data']['nftItems']['items']:
#         name = nft['name']
#         address = nft['address']
#         sale = nft.get('sale')
#         if sale:
#             typename = sale['__typename']
#             if typename in ["NftSaleFixPrice", "NftSaleFixPriceDisintar"]:
#                 try:
#                     price = int(sale['fullPrice']) / 1e9
#                     print(f"{name} ({address}) [{typename}]: {price} TON")
#                 except:
#                     print(f"{name} ({address}) [{typename}]: Invalid price format")
#             else:
#                 print(f"{name} ({address}) [{typename}]: Price not supported")
#         else:
#             print(f"{name} ({address}): Not for sale")