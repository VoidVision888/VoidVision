import os
import logging
from decimal import Decimal
from web3 import Web3
from eth_account import Account

from backend.workers.polygon_signer import build_and_send_polygon_usdc_tx, TREASURY_MULTISIG_ADDRESS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FeeSweepWorker")

ROUTING_FEE_RATE = Decimal("0.001")   
SUCCESS_SHARE_RATE = Decimal("0.0025") 

class FeeSweepWorker:
    def __init__(self, private_key: str):
        self.private_key = private_key
        self.w3 = Web3(Web3.HTTPProvider(os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")))
        if not self.w3.is_connected():
            raise ConnectionError("无法连接到 Polygon RPC 节点，请检查网络。")
        
        self.account = Account.from_key(private_key)
        self.wallet_address = self.account.address
        logger.info(f"清算 Worker 初始化成功 | 监控钱包: {self.wallet_address}")

    def calculate_fees(self, stake: Decimal, payout: Decimal) -> tuple[Decimal, Decimal]:
        routing_fee = stake * ROUTING_FEE_RATE
        net_profit = payout - stake
        success_share = Decimal("0")
        if net_profit > 0:
            success_share = net_profit * SUCCESS_SHARE_RATE
        return routing_fee.quantize(Decimal("0.000001")), success_share.quantize(Decimal("0.000001"))

    def execute_fee_sweep(self, stake: Decimal, payout: Decimal, event_name: str) -> str | None:
        routing_fee, success_share = self.calculate_fees(stake, payout)
        total_fee = routing_fee + success_share
        
        if total_fee <= 0:
            logger.info(f"[{event_name}] 本笔交易无需扣除手续费。")
            return None

        try:
            logger.info(f"[{event_name}] 正在触发微额清算 | 路由费: {routing_fee} | 盈利分润: {success_share} | 总计: {total_fee} USDC")
            tx_hash_hex = build_and_send_polygon_usdc_tx(
                private_key=self.private_key,
                recipient_address=TREASURY_MULTISIG_ADDRESS,
                amount_in_usdc=total_fee
            )
            logger.info(f"✅ 自动清算成功上链！赛事: {event_name} | TxHash: {tx_hash_hex}")
            return tx_hash_hex
        except Exception as e:
            logger.error(f"❌ 自动清算转账失败 [{event_name}]: {str(e)}")
            return None

if __name__ == "__main__":
    TEST_PK = os.getenv("CLIENT_PRIVATE_KEY", "0x0000000000000000000000000000000000000000000000000000000000000000")
    try:
        worker = FeeSweepWorker(TEST_PK)
        logger.info("FeeSweepWorker 自动化触发链路已成功加载。")
    except Exception as ex:
        logger.info(f"模块加载提示: {ex}")
