import os
import time
import logging
from decimal import Decimal
from web3 import Web3
from eth_account import Account

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FeeSweepWorker")

# ==================== 核心配置常量 ====================
POLYGON_RPC_URL = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
# Polymarket 常用的 USDC.e / USDC 合约地址（Polygon 链）
USDC_CONTRACT_ADDRESS = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")
# 平台多签金库地址 (Safe Multi-Sig)
TREASURY_MULTISIG = Web3.to_checksum_address("0xYourMultiSigTreasuryAddressHere")

# 费率标准
ROUTING_FEE_RATE = Decimal("0.001")   # 0.1% 管道路由费
SUCCESS_SHARE_RATE = Decimal("0.0025") # 0.25% 盈利分成

# ERC20 标准 Transfer ABI
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]

class FeeSweepWorker:
    def __init__(self, private_key: str):
        self.w3 = Web3(Web3.HTTPProvider(POLYGON_RPC_URL))
        if not self.w3.is_connected():
            raise ConnectionError("无法连接到 Polygon RPC 节点，请检查网络或 RPC 地址。")
        
        self.account = Account.from_key(private_key)
        self.wallet_address = self.account.address
        self.usdc_contract = self.w3.eth.contract(address=USDC_CONTRACT_ADDRESS, abi=ERC20_ABI)
        
        logger.info(f"清算 Worker 初始化成功 | 监控钱包: {self.wallet_address}")

    def check_gas_balance(self) -> bool:
        """检查客户端钱包的原生 POL/MATIC 余额是否足够支付 Gas 费"""
        native_balance = self.w3.eth.get_balance(self.wallet_address)
        min_gas_required = self.w3.to_wei(0.005, 'ether') # 预留 0.005 POL 作为 Gas
        
        if native_balance < min_gas_required:
            logger.warning(f"⚠️ 钱包原生代币余额过低 (当前: {self.w3.from_wei(native_balance, 'ether')} POL)，请及时充值以防分润转账失败！")
            return False
        return True

    def calculate_fees(self, stake: Decimal, payout: Decimal) -> tuple[Decimal, Decimal]:
        """
        计算双重费用：
        1. 路由费 = 本金 * 0.1%
        2. 盈利分成 = 净利润 * 0.25% (若未盈利则为 0)
        """
        routing_fee = stake * ROUTING_FEE_RATE
        
        net_profit = payout - stake
        success_share = Decimal("0")
        if net_profit > 0:
            success_share = net_profit * SUCCESS_SHARE_RATE
            
        return routing_fee.quantize(Decimal("0.000001")), success_share.quantize(Decimal("0.000001"))

    def execute_fee_sweep(self, stake: Decimal, payout: Decimal, event_name: str) -> str | None:
        """
        核心清算方法：在订单结算瞬间自动触发 USDC 微转账至多签金库
        """
        routing_fee, success_share = self.calculate_fees(stake, payout)
        total_fee = routing_fee + success_share
        
        if total_fee <= 0:
            logger.info(f"[{event_name}] 本笔交易无需扣除手续费。")
            return None

        # 1. 检查 Gas 余额
        if not self.check_gas_balance():
            logger.error("Gas 不足，本次自动清算暂缓。")
            return None

        # 2. 转换成 USDC 6位小数的整数
        fee_amount_wei = int(total_fee * Decimal(10**6))
        
        try:
            # 3. 构造 ERC-20 transfer 交易
            nonce = self.w3.eth.get_transaction_count(self.wallet_address)
            
            tx = self.usdc_contract.functions.transfer(
                TREASURY_MULTISIG,
                fee_amount_wei
            ).build_transaction({
                'chainId': 137, # Polygon Chain ID
                'gas': 65000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
            })

            # 4. 本地私钥签名
            signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=self.account.key)
            
            # 5. 广播交易上链
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = self.w3.to_hex(tx_hash)
            
            logger.info(f"✅ 成功扣除管道分润 | 赛事: {event_name} | 总抽佣: {total_fee} USDC | TxHash: {tx_hash_hex}")
            
            # TODO: 将 tx_hash_hex、routing_fee、success_share 写入 PostgreSQL 的 execution_ledger 表
            
            return tx_hash_hex

        except Exception as e:
            logger.error(f"❌ 自动清算转账失败 [{event_name}]: {str(e)}")
            # TODO: 记录错误到挂账表（Pending Debt），等待下次盈利回款时补扣
            return None

# ==================== 测试调用示例 ====================
if __name__ == "__main__":
    # 测试私钥（生产环境中从安全的加密配置读取）
    TEST_PRIVATE_KEY = os.getenv("CLIENT_PRIVATE_KEY", "0x0000000000000000000000000000000000000000000000000000000000000000")
    
    try:
        worker = FeeSweepWorker(TEST_PRIVATE_KEY)
        # 模拟一笔：本金 25 USDC，回款 35 USDC (盈利 10 USDC) 的赛事结算
        worker.execute_fee_sweep(stake=Decimal("25.0"), payout=Decimal("35.0"), event_name="Arsenal vs Chelsea")
    except Exception as ex:
        logger.info(f"测试运行提示: {ex}")
