import os
from decimal import Decimal
from web3 import Web3
from eth_account import Account

# ==================== 1. Polygon 链与合约基础配置 ====================
# Polygon 官方或可靠的 RPC 节点
POLYGON_PRC_URL = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")

# Polygon 链上的官方 USDC 合约地址（注意：Polymarket 体系在 Polygon 上主要使用 USDC.e 或原生 USDC）
USDC_CONTRACT_ADDRESS = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")

# 你的平台多签金库地址 (Safe / 多签钱包)
TREASURY_MULTISIG_ADDRESS = Web3.to_checksum_address("0xYourMultiSigTreasuryAddressHere")

# 标准 ERC-20 转账 ABI（只需要 transfer 和 balanceOf 即可）
ERC20_TRANSFER_ABI = [
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

# ==================== 2. 核心签名与广播模板函数 ====================
def build_and_send_polygon_usdc_tx(private_key: str, recipient_address: str, amount_in_usdc: Decimal) -> str:
    """
    Polygon 链专属的 web3.py 签名与广播模板
    :param private_key: 客户端本地私钥 (Hex 格式，带或不带 0x 均可)
    :param recipient_address: 收款方地址（多签金库）
    :param amount_in_usdc: 需要转账的 USDC 金额（例如 0.025 代表 0.025 USDC）
    :return: 交易成功后的哈希值 (TxHash Hex)
    """
    # 初始化 Web3 连接
    w3 = Web3(Web3.HTTPProvider(POLYGON_PRC_URL))
    if not w3.is_connected():
        raise ConnectionError("无法连接至 Polygon 网络节点，请检查 RPC 状态。")

    # 通过私钥加载账户
    sender_account = Account.from_key(private_key)
    sender_address = sender_account.address

    # 实例化 USDC 合约
    usdc_contract = w3.eth.contract(
        address=USDC_CONTRACT_ADDRESS, 
        abi=ERC20_TRANSFER_ABI
    )

    # 将人类可读的 USDC 金额转换为 6 位小数的链上整数 (Wei 级别)
    # 例如：0.025 USDC * 10^6 = 25000
    amount_in_wei = int(amount_in_usdc * Decimal(10**6))

    # 获取当前账户的 nonce（防重放攻击）
    nonce = w3.eth.get_transaction_count(sender_address)

    # 动态获取当前的 gas_price（Polygon 链通常比较便宜，但也需要动态匹配）
    gas_price = w3.eth.gas_price

    # 步骤 A：构建未签名的标准 ERC-20 交易字典
    tx_data = usdc_contract.functions.transfer(
        Web3.to_checksum_address(recipient_address),
        amount_in_wei
    ).build_transaction({
        'chainId': 137,             # Polygon 主网 Chain ID 强制锁定为 137
        'gas': 65000,               # ERC-20 转账的标准 gas 上限足够
        'gasPrice': gas_price,      # 当前网络实际 Gas 价格
        'nonce': nonce,             # 当前账户 nonce 序列号
    })

    # 步骤 B：使用客户端本地私钥对交易进行 EIP-155 / 标准签名
    signed_txn = w3.eth.account.sign_transaction(tx_data, private_key=sender_account.key)

    # 步骤 C：将签名后的原始交易广播到 Polygon 链上
    raw_tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    
    # 转换为 16 进制的哈希字符串
    tx_hash_hex = w3.to_hex(raw_tx_hash)
    
    return tx_hash_hex

# ==================== 3. 模板本地联调测试（可直接运行） ====================
if __name__ == "__main__":
    # 模拟测试：请勿在生产环境明文硬编码私钥
    SAMPLE_PK = "0x0000000000000000000000000000000000000000000000000000000000000000"
    
    try:
        print("正在测试构建 Polygon 签名模板...")
        # 模拟划转 0.1 USDC 到多签金库
        # tx_hash = build_and_send_polygon_usdc_tx(SAMPLE_PK, TREASURY_MULTISIG_ADDRESS, Decimal("0.1"))
        # print(f"测试广播成功，交易哈希: {tx_hash}")
    except Exception as e:
        print(f"模板运行示例捕获异常: {e}")
