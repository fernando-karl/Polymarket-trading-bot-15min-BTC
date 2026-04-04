"""
Simple script to test Polymarket balance retrieval.
"""
import os
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

load_dotenv()

def main():
    # Load configuration
    host = "https://clob.polymarket.com"
    private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
    api_key = os.getenv("POLYMARKET_API_KEY")
    api_secret = os.getenv("POLYMARKET_API_SECRET")
    api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE")
    signature_type = int(os.getenv("POLYMARKET_SIGNATURE_TYPE", "2"))
    funder = os.getenv("POLYMARKET_FUNDER", "")

    print("=" * 70)
    print("POLYMARKET BALANCE TEST")
    print("=" * 70)
    print(f"Host: {host}")
    print(f"Signature Type: {signature_type}")
    print(f"Private Key: {'✓' if private_key else '✗'}")
    print(f"API Key: {'✓' if api_key else '✗'}")
    print(f"API Secret: {'✓' if api_secret else '✗'}")
    print(f"API Passphrase: {'✓' if api_passphrase else '✗'}")
    print("=" * 70)

    try:
        # Create client
        print("\n1. Creating ClobClient...")
        client = ClobClient(
            host,
            key=private_key,
            chain_id=137,
            signature_type=signature_type,
            funder=funder or None
        )
        print("   ✓ Client created")

        # Derive credentials from private key
        print("\n2. Deriving API credentials from private key...")
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        print(f"   ✓ API Key: {creds.api_key}")
        print(f"   ✓ Credentials configured")

        # Get wallet address
        print("\n3. Getting wallet address...")
        address = client.get_address()
        print(f"   ✓ Signer address: {address}")
        if funder:
            print(f"   ✓ Funder (proxy): {funder}")

        # Get balance - Method 1: COLLATERAL (USDC) via CLOB API
        print("\n4. Getting USDC balance via CLOB API (COLLATERAL)...")
        try:
            from py_clob_client.clob_types import AssetType, BalanceAllowanceParams

            params = BalanceAllowanceParams(
                asset_type=AssetType.COLLATERAL,
                signature_type=signature_type
            )
            result = client.get_balance_allowance(params)
            print(f"   Raw response: {result}")

            if isinstance(result, dict):
                balance_raw = result.get("balance", "0")
                balance_wei = float(balance_raw)
                balance_usdc = balance_wei / 1_000_000

                print(f"   Balance raw: {balance_raw}")
                print(f"   💰 CLOB BALANCE: ${balance_usdc:.6f}")
            else:
                print(f"   ⚠️ Unexpected response type: {type(result)}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
            import traceback
            traceback.print_exc()

        # Verify balance on-chain via Polygon JSON-RPC (no extra dependencies)
        print("\n5. Checking on-chain USDC balances (Polygon JSON-RPC)...")
        try:
            import httpx

            usdc_contracts = {
                "USDC (native)": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
                "USDC.e (bridged)": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            }

            addresses_to_check = {"Signer": address}
            if funder and funder.lower() != address.lower():
                addresses_to_check["Funder (proxy)"] = funder

            for addr_label, addr in addresses_to_check.items():
                for token_label, contract_addr in usdc_contracts.items():
                    addr_padded = addr.lower().replace("0x", "").zfill(64)
                    call_data = "0x70a08231" + addr_padded
                    payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "eth_call",
                        "params": [
                            {"to": contract_addr, "data": call_data},
                            "latest",
                        ],
                    }
                    resp = httpx.post(
                        "https://polygon-bor-rpc.publicnode.com",
                        json=payload,
                        timeout=10,
                    )
                    rpc_result = resp.json().get("result", "0x0")
                    balance_wei = int(rpc_result, 16)
                    balance_usd = balance_wei / 1_000_000
                    marker = "💰" if balance_usd > 0 else "  "
                    print(f"   {marker} {addr_label} / {token_label}: ${balance_usd:.6f}")
        except Exception as e:
            print(f"   ⚠️ Could not check on-chain: {e}")

        print("\n" + "=" * 70)
        print("TEST COMPLETED")
        print("=" * 70)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
