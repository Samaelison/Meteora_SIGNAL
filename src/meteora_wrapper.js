

require("dotenv").config({ path: "E:/MeteoraMeme/meteora_bot/config/secrets.env" });

const express = require("express");
const bodyParser = require("body-parser");
const {
  Connection,
  PublicKey,
  Keypair,
  sendAndConfirmTransaction,
} = require("@solana/web3.js");
const BN = require("bn.js");
const bs58 = require("bs58");
const {
  getMint,
  getOrCreateAssociatedTokenAccount,
} = require("@solana/spl-token");
const DLMM = require("@meteora-ag/dlmm").default || require("@meteora-ag/dlmm");

const app = express();
const PORT = 3000;

app.use(bodyParser.json());

console.log("=== Meteora Wrapper Starting ===");
console.log("Node.js version:", process.version);

let meteoraVersion = null;
try {
  meteoraVersion = require("@meteora-ag/dlmm/package.json").version;
  console.log("Meteora DLMM version:", meteoraVersion);
} catch (err) {
  // ignore
}

const rpcEndpoint = process.env.SOLANA_RPC_ENDPOINT;
const connection = new Connection(rpcEndpoint, "confirmed");
console.log("Using RPC endpoint:", rpcEndpoint);

const secretKeyStr = process.env.SOLANA_PRIVATE_KEY;
if (!secretKeyStr) {
  throw new Error("SOLANA_PRIVATE_KEY not found in env");
}
const secretKey = bs58.decode(secretKeyStr);
const keypair = Keypair.fromSecretKey(secretKey);
console.log("Server Keypair Pubkey:", keypair.publicKey.toBase58());

const DEBUG_LOGS = (process.env.DEBUG_LOGS === "true");


async function sendAndConfirmOnce(connection, transaction, signers, options) {
  try {
  
    return await sendAndConfirmTransaction(connection, transaction, signers, options);
  } catch (err) {
    console.warn(`[sendAndConfirmOnce] => ${err.message}`);
    throw err;
  }
}


async function loadDecimals(dlmmPool) {
  const wsolMintStr = "So11111111111111111111111111111111111111112";

  const mintX = dlmmPool.tokenX.publicKey.toBase58();
  const mintY = dlmmPool.tokenY.publicKey.toBase58();

  if (mintX === wsolMintStr) {
    dlmmPool.tokenX.decimals = 9;
    if (DEBUG_LOGS) console.log("tokenX is wSOL => decimals=9");
  } else {
    const mintInfoX = await getMint(connection, new PublicKey(mintX));
    dlmmPool.tokenX.decimals = mintInfoX.decimals;
    if (DEBUG_LOGS) console.log(`Loaded decimals for tokenX ${mintX} => ${mintInfoX.decimals}`);
  }

  if (mintY === wsolMintStr) {
    dlmmPool.tokenY.decimals = 9;
    if (DEBUG_LOGS) console.log("tokenY is wSOL => decimals=9");
  } else {
    const mintInfoY = await getMint(connection, new PublicKey(mintY));
    dlmmPool.tokenY.decimals = mintInfoY.decimals;
    if (DEBUG_LOGS) console.log(`Loaded decimals for tokenY ${mintY} => ${mintInfoY.decimals}`);
  }

  if (DEBUG_LOGS) {
    console.log(
      "Final decimals => tokenX.decimals=",
      dlmmPool.tokenX.decimals,
      "tokenY.decimals=",
      dlmmPool.tokenY.decimals
    );
  }
}


app.post("/list_bins_around", async (req, res) => {
  try {
    const { poolAddress } = req.body;
    if (!poolAddress) {
      return res.status(400).json({ error: "Missing poolAddress" });
    }

    // 1) Инициализируем пул
    const poolPubkey = new PublicKey(poolAddress);
    const dlmmPool = await DLMM.create(connection, poolPubkey);
    await dlmmPool.refetchStates();

    // 2) Получаем activeBin
    const activeBinInfo = await dlmmPool.getActiveBin();
    let activeBinId = null;
    let activeBinPrice = null;
    if (activeBinInfo && activeBinInfo.binId != null) {
      activeBinId =
        typeof activeBinInfo.binId === "number"
          ? activeBinInfo.binId
          : activeBinInfo.binId.toNumber();
      activeBinPrice = activeBinInfo.price || null;
    }

    console.log(`[list_bins_around] activeBin => id=${activeBinId}, price=${activeBinPrice}`);

    // 3) Запрашиваем бины +-70
    const leftCount = 70;
    const rightCount = 70;
    const binsData = await dlmmPool.getBinsAroundActiveBin(leftCount, rightCount);
    const { activeBin, bins } = binsData || {};
    console.log(`[list_bins_around] getBinsAroundActiveBin(${leftCount},${rightCount}) => activeBin=${activeBin}, bins.length=${bins?.length}`);

    // Ищем индекс активного бина в полученном массиве
    let activeIndex = -1;
    if (bins && bins.length > 0) {
      activeIndex = bins.findIndex((b) => {
        // b.binId может быть BN: сравним как number
        if (typeof b.binId.toNumber === "function") {
          return b.binId.toNumber() === activeBinId;
        }
        return b.binId === activeBinId;
      });
    }

    // Логируем ровно 3 бина для отладки
    if (activeIndex >= 0 && bins && bins.length > 0) {
      // bin "left"
      if (activeIndex - 1 >= 0) {
        const bLeft = bins[activeIndex - 1];
        console.log(`   left bin => binId=${bLeft.binId}, xAmount=${bLeft.xAmount}, yAmount=${bLeft.yAmount}, price=${bLeft.price}`);
      }
      // bin "active"
      {
        const bAct = bins[activeIndex];
        console.log(`   active bin => binId=${bAct.binId}, xAmount=${bAct.xAmount}, yAmount=${bAct.yAmount}, price=${bAct.price}`);
      }
      // bin "right"
      if (activeIndex + 1 < bins.length) {
        const bRight = bins[activeIndex + 1];
        console.log(`   right bin => binId=${bRight.binId}, xAmount=${bRight.xAmount}, yAmount=${bRight.yAmount}, price=${bRight.price}`);
      }
    } else {
      console.log("   [list_bins_around] could not find activeIndex in bins array!");
    }

    // Возвращаем все bins в ответ
    return res.json({
      activeBinId,
      activeBinPrice,
      totalBins: bins?.length || 0,
      bins: (bins || []).map((b) => ({
        binId: b.binId.toString ? b.binId.toString() : String(b.binId),
        xAmount: b.xAmount.toString(),
        yAmount: b.yAmount.toString(),
        price: b.price?.toString?.() || null
      }))
    });
  } catch (err) {
    console.error("Error in /list_bins_around =>", err);
    return res.status(500).json({ error: err.message || err.toString() });
  }
});


app.post("/swap_with_price_impact", async (req, res) => {
  try {
    const { lbPair, amountIn, swapYtoX, priceImpactBps } = req.body;
    if (!lbPair || !amountIn || swapYtoX === undefined || !priceImpactBps) {
      return res.status(400).json({ error: "Missing required parameter(s)" });
    }

    console.log("\n=== [swap_with_price_impact] START ===\n");
    console.log(`Input params => lbPair=${lbPair}, amountIn=${amountIn}, swapYtoX=${swapYtoX}, priceImpactBps=${priceImpactBps}`);

    // 1) Инициализируем пул
    const poolPubkey = new PublicKey(lbPair);
    const dlmmPool = await DLMM.create(connection, poolPubkey);

    if (DEBUG_LOGS) {
      console.log(
        "DLMM pool tokens => X:",
        dlmmPool.tokenX.publicKey.toBase58(),
        "Y:",
        dlmmPool.tokenY.publicKey.toBase58()
      );
    }

    await dlmmPool.refetchStates();

    try {
      const disabled = dlmmPool.isSwapDisabled
        ? dlmmPool.isSwapDisabled()
        : false;
      if (DEBUG_LOGS) console.log("dlmmPool.isSwapDisabled =", disabled);
    } catch (err) {
      if (DEBUG_LOGS) console.log("Error reading isSwapDisabled =>", err);
    }

    // 2) Логируем activeBin
    let activeBin = null;
    try {
      activeBin = await dlmmPool.getActiveBin();
      console.log(`ActiveBin: id=${activeBin?.binId}, price=${activeBin?.price}`);
    } catch (e) {
      if (DEBUG_LOGS) console.log("Error getActiveBin =>", e);
    }

    // 3) Загрузим decimals
    await loadDecimals(dlmmPool);
    const decimalsX = dlmmPool.tokenX.decimals;
    const decimalsY = dlmmPool.tokenY.decimals;

    // 4) Определяем inAmount
    const priceImpactBN = new BN(parseInt(priceImpactBps, 10));
    let inAmountBN;

    if (swapYtoX) {
      // SOL->Token
      const parsedSOL = parseFloat(amountIn);
      const lamports = Math.floor(parsedSOL * 10 ** decimalsY);
      inAmountBN = new BN(lamports);
      console.log(`SwapYtoX=true => inAmountBN=${inAmountBN.toString()} (SOL)`);
    } else {
      // Token->SOL
      console.log("SwapYtoX=false => ignoring 'amountIn', fetch entire tokenX balance");
      const tokenXPubkey = dlmmPool.tokenX.publicKey;
      const xAta = await getOrCreateAssociatedTokenAccount(
        connection,
        keypair,
        tokenXPubkey,
        keypair.publicKey
      );
      const balInfo = await connection.getTokenAccountBalance(
        xAta.address,
        "confirmed"
      );
      const fullAmountStr = balInfo.value.amount;
      inAmountBN = new BN(fullAmountStr);
      console.log(`Full tokenX balance BN => ${inAmountBN.toString()}`);
    }

    console.log(`priceImpactBN=${priceImpactBN.toString()}`);

    // 5) bin arrays
    let autoBinArrays = null;
    try {
      if (DEBUG_LOGS) console.log("getBinArrayForSwap(...,2) =>");
      autoBinArrays = await dlmmPool.getBinArrayForSwap(swapYtoX, 2);
      if (DEBUG_LOGS) {
        if (!autoBinArrays || autoBinArrays.length === 0) {
          console.log("getBinArrayForSwap => empty!");
        } else {
          console.log(`getBinArrayForSwap => got ${autoBinArrays.length} bin arrays`);
        }
      }
    } catch (binErr) {
      console.warn("[swap_with_price_impact] getBinArrayForSwap error =>", binErr);
    }

    let binArrayPubkeys = null;
    if (autoBinArrays && autoBinArrays.length > 0) {
      binArrayPubkeys = autoBinArrays.map((obj) => new PublicKey(obj.publicKey));
      if (DEBUG_LOGS) {
        console.log("binArrayPubkeys =>", binArrayPubkeys.map(pk => pk.toBase58()));
      }
    }

    let inTokenPubkey, outTokenPubkey;
    if (swapYtoX) {
      // Y->X => inToken=Y, outToken=X
      inTokenPubkey = dlmmPool.tokenY.publicKey;
      outTokenPubkey = dlmmPool.tokenX.publicKey;
    } else {
      // X->Y => inToken=X, outToken=Y
      inTokenPubkey = dlmmPool.tokenX.publicKey;
      outTokenPubkey = dlmmPool.tokenY.publicKey;
    }

    console.log("[swap_with_price_impact] Building transaction...");

    // Генерируем транзакцию swapWithPriceImpact
    const transaction = await dlmmPool.swapWithPriceImpact({
      inToken: inTokenPubkey,
      outToken: outTokenPubkey,
      inAmount: inAmountBN,
      priceImpact: priceImpactBN,
      lbPair: dlmmPool.pubkey,
      user: keypair.publicKey,
      binArraysPubkey: binArrayPubkeys || undefined,
    });

    console.log("[swap_with_price_impact] Sending transaction...");

    const txSignature = await sendAndConfirmOnce(
      connection,
      transaction,
      [keypair],
      { skipPreflight: false, commitment: "confirmed" }
    );

    console.log(`[swap_with_price_impact] Tx signature = ${txSignature}`);

    // Читаем баланс выходного токена
    let finalTokenBalance = null;
    try {
      const outAta = await getOrCreateAssociatedTokenAccount(
        connection,
        keypair,
        outTokenPubkey,
        keypair.publicKey,
        true
      );
      const outBal = await connection.getTokenAccountBalance(outAta.address, "confirmed");
      finalTokenBalance = outBal.value.uiAmountString;
      if (DEBUG_LOGS) {
        console.log("Final out token balance =>", finalTokenBalance);
      }
    } catch (err) {
      if (DEBUG_LOGS) console.log("Error reading final out token balance =>", err);
    }

    // Итоговый SOL
    const balancePost = await connection.getBalance(keypair.publicKey, "confirmed");
    const balanceSolPost = balancePost / 1e9;

    console.log("=== [swap_with_price_impact] END ===\n");
    return res.json({
      txSignature,
      finalOutTokenBalance: finalTokenBalance,
      finalSolBalance: balanceSolPost,
      message: "swapWithPriceImpact completed."
    });
  } catch (err) {
    console.error("[swap_with_price_impact] Full error =>", err);
    if (err && err.stack) {
      console.error("Error stack =>", err.stack);
    }
    res.status(500).json({ error: err.toString() });
  }
});



/**
 * POST /add_liquidity_spot
 * - Создаёт новую позицию
 * - Добавляет одностороннюю ликвидность (только SOL = Y)
 * - Диапазон бинов => [activeBinId - 69, activeBinId - 1]
 */
app.post("/add_liquidity_spot", async (req, res) => {
  try {
    // Получаем strategyType "снаружи"
    const { lbPair, amountSol, strategyType } = req.body;
    if (!lbPair || !amountSol || strategyType === undefined) {
      return res.status(400).json({ error: "Missing required parameter(s)" });
    }

    const stType = parseInt(strategyType, 10);

    // 1) Инициализируем пул
    const poolPubkey = new PublicKey(lbPair);
    const dlmmPool = await DLMM.create(connection, poolPubkey);
    await dlmmPool.refetchStates();

    // 2) Узнаём activeBin
    const activeBinInfo = await dlmmPool.getActiveBin();
    const activeBinId = typeof activeBinInfo.binId === "number"
      ? activeBinInfo.binId
      : activeBinInfo.binId.toNumber();

    // minBinId / maxBinId
    const minBinId = activeBinId - 69;
    const maxBinId = activeBinId - 1;

    console.log(`/add_liquidity_spot => range [${minBinId}, ${maxBinId}] for lbPair=${lbPair}`);

    // 3) Генерируем Keypair для новой позиции
    const newPositionKeypair = Keypair.generate();

    // 4) Считаем totalYAmount (lamports) – "amountSol"
    const parsedSol = parseFloat(amountSol);
    const totalYAmount = new BN(Math.floor(parsedSol * 1e9));
    const totalXAmount = new BN(0); // одностороннее => X=0

    // 5) Формируем транзакцию initializePositionAndAddLiquidityByStrategy
    const createPositionTx = await dlmmPool.initializePositionAndAddLiquidityByStrategy({
      positionPubKey: newPositionKeypair.publicKey,
      user: keypair.publicKey,
      totalXAmount,
      totalYAmount,
      strategy: {
        minBinId,
        maxBinId,
        strategyType: stType
      },
    });

    // 6) Отправляем транзакцию (подписываем владельцем и позицией)
    const txSignature = await sendAndConfirmOnce(
      connection,
      createPositionTx,
      [keypair, newPositionKeypair],
      { skipPreflight: false, commitment: "confirmed" }
    );

    return res.json({
      txSignature,
      positionPubkey: newPositionKeypair.publicKey.toBase58(),
      message: "add_liquidity_spot completed."
    });
  } catch (error) {
    console.error("Error in /add_liquidity_spot =>", error);
    return res.status(500).json({ error: error.toString() });
  }
});

/**
 * POST /add_liquidity_x_only
 * - Создаёт новую позицию
 * - Добавляет одностороннюю ликвидность (только X)
 * - Диапазон бинов => [activeBinId+1, activeBinId+69]  (выше текущей цены)
 * - При этом totalXAmount = весь доступный X на кошельке
 */
app.post("/add_liquidity_x_only", async (req, res) => {
  try {
    const { lbPair, strategyType } = req.body;
    if (!lbPair || strategyType === undefined) {
      return res.status(400).json({ error: "Missing lbPair or strategyType" });
    }
    const stType = parseInt(strategyType, 10);

    // 1) Инициализируем пул
    const poolPubkey = new PublicKey(lbPair);
    const dlmmPool = await DLMM.create(connection, poolPubkey);
    await dlmmPool.refetchStates();

    // 2) Узнаём activeBin
    const activeBinInfo = await dlmmPool.getActiveBin();
    const activeBinId = typeof activeBinInfo.binId === "number"
      ? activeBinInfo.binId
      : activeBinInfo.binId.toNumber();

    // minBinId / maxBinId (выше цены)
    const minBinId = activeBinId + 1;
    const maxBinId = activeBinId + 69;

    console.log(`/add_liquidity_x_only => range [${minBinId}, ${maxBinId}] for lbPair=${lbPair}`);

    // 3) Генерируем Keypair для новой позиции
    const newPositionKeypair = Keypair.generate();

    // 4) Узнаём весь баланс X
    await loadDecimals(dlmmPool);
    const xMintPubkey = dlmmPool.tokenX.publicKey;
    const xAta = await getOrCreateAssociatedTokenAccount(
      connection,
      keypair,
      xMintPubkey,
      keypair.publicKey
    );
    const balInfo = await connection.getTokenAccountBalance(
      xAta.address,
      "confirmed"
    );
    const fullAmountStr = balInfo.value.amount;
    const fullAmountBN = new BN(fullAmountStr);

    const totalXAmount = fullAmountBN; // весь X
    const totalYAmount = new BN(0);

    console.log(`   Found X mint = ${xMintPubkey.toBase58()}, decimals=${dlmmPool.tokenX.decimals}, going to deposit fullX=${fullAmountBN.toString()}`);

    // 5) Формируем транзакцию
    const createPositionTx = await dlmmPool.initializePositionAndAddLiquidityByStrategy({
      positionPubKey: newPositionKeypair.publicKey,
      user: keypair.publicKey,
      totalXAmount,
      totalYAmount,
      strategy: {
        minBinId,
        maxBinId,
        strategyType: stType
      },
    });

    // 6) Отправляем транзакцию
    const txSignature = await sendAndConfirmOnce(
      connection,
      createPositionTx,
      [keypair, newPositionKeypair],
      { skipPreflight: false, commitment: "confirmed" }
    );

    return res.json({
      txSignature,
      positionPubkey: newPositionKeypair.publicKey.toBase58(),
      fullXDeposit: totalXAmount.toString(),
      message: "add_liquidity_x_only completed."
    });
  } catch (error) {
    console.error("Error in /add_liquidity_x_only =>", error);
    return res.status(500).json({ error: error.toString() });
  }
});

/**
 * POST /get_position_info
 * - Возвращает детальную информацию о конкретной позиции (по positionPubkey)
 */
app.post("/get_position_info", async (req, res) => {
  try {
    const { lbPair, positionPubkey } = req.body;
    if (!lbPair || !positionPubkey) {
      return res.status(400).json({ error: "Missing required parameter(s)" });
    }

    const poolPubkey = new PublicKey(lbPair);
    const dlmmPool = await DLMM.create(connection, poolPubkey);
    await dlmmPool.refetchStates();

    // Логируем активный бин (необязательно, для отладки)
    const currentActiveBin = await dlmmPool.getActiveBin();
    console.log(`   Active bin: id=${currentActiveBin?.binId}, xAmount=${currentActiveBin?.xAmount}, yAmount=${currentActiveBin?.yAmount}, price=${currentActiveBin?.price}`);

    // Запрашиваем все позиции юзера по этому пулу
    const { userPositions } = await dlmmPool.getPositionsByUserAndLbPair(keypair.publicKey);

    // Ищем нужную
    const positionKey = new PublicKey(positionPubkey);
    const userPosition = userPositions.find((pos) => pos.publicKey.equals(positionKey));
    if (!userPosition) {
      return res.status(404).json({ error: "Position not found" });
    }

    // Просто возвращаем сырые данные
    const result = {
      positionPubkey: positionPubkey,
      positionData: userPosition.positionData
    };

    return res.json(result);
  } catch (error) {
    console.error("Error in /get_position_info =>", error);
    return res.status(500).json({ error: error.toString() });
  }
});

/**
 * POST /remove_liquidity_and_close
 * Удаляет ликвидность (100%), закрывает позицию
 */
app.post("/remove_liquidity_and_close", async (req, res) => {
  try {
    const { lbPair, positionPubkey } = req.body;
    if (!lbPair || !positionPubkey) {
      return res.status(400).json({ error: "Missing required parameter(s)" });
    }

    // 1) Создаём DLMM pool
    const poolPubkey = new PublicKey(lbPair);
    const dlmmPool = await DLMM.create(connection, poolPubkey);
    await dlmmPool.refetchStates();

    // 2) Ищем нужную позицию у текущего keypair
    const { userPositions } = await dlmmPool.getPositionsByUserAndLbPair(keypair.publicKey);

    const positionKey = new PublicKey(positionPubkey);
    const userPosition = userPositions.find((pos) => pos.publicKey.equals(positionKey));
    if (!userPosition) {
      return res.status(404).json({ error: "Position not found" });
    }

    // Собираем binIds (number[]) – стандартный подход
    const binIdsToRemove = userPosition.positionData.positionBinData.map((bin) => {
      const binIdNum = (typeof bin.binId === "string")
         ? parseInt(bin.binId, 10)
         : bin.binId;
      return binIdNum;
    });

    console.log("Bin IDs to remove (numbers):", binIdsToRemove);

    // Удаляем 100% ликвидности: bps=100% => new BN(10000)
    const bpsToRemove = new BN(10000);

    // removeLiquidity (закрыть позицию)
    const removeLiquidityTxOrTxs = await dlmmPool.removeLiquidity({
      position: userPosition.publicKey,
      user: keypair.publicKey,
      binIds: binIdsToRemove,
      bps: bpsToRemove,
      shouldClaimAndClose: true,
    });

    // Может вернуть массив транзакций
    const txArray = Array.isArray(removeLiquidityTxOrTxs)
      ? removeLiquidityTxOrTxs
      : [removeLiquidityTxOrTxs];

    // Отправляем
    const txSignatures = [];
    for (const tx of txArray) {
      const sig = await sendAndConfirmOnce(
        connection,
        tx,
        [keypair],
        { skipPreflight: false, commitment: "confirmed" }
      );
      txSignatures.push(sig);
    }

    // ==== Новая логика: узнаём итоговый SOL и итоговый X ====
    let finalSolBalance = 0;
    let finalXBalance = "0";

    try {
      // SOL
      const lamports = await connection.getBalance(keypair.publicKey, "confirmed");
      finalSolBalance = lamports / 1e9;
    } catch (err) {
      console.warn("Error fetching final SOL balance =>", err);
    }

    try {
      // X
      const tokenXPubkey = dlmmPool.tokenX.publicKey;
      const userXAta = await getOrCreateAssociatedTokenAccount(
        connection,
        keypair,
        tokenXPubkey,
        keypair.publicKey,
        true
      );
      const balInfo = await connection.getTokenAccountBalance(userXAta.address, "confirmed");
      finalXBalance = balInfo.value.uiAmountString;
    } catch (err) {
      console.warn("Error fetching final X balance =>", err);
    }

    return res.json({
      txSignatures,
      finalSolBalance,
      finalXBalance,
      message: "remove_liquidity_and_close completed (via bps=100% approach)."
    });

  } catch (error) {
    console.error("Error in /remove_liquidity_and_close =>", error);
    return res.status(500).json({ error: error.toString() });
  }
});

/**
 * POST /shutdown
 */
app.post("/shutdown", (req, res) => {
  res.json({ message: "Server shutting down gracefully." });
  server.close(() => {
    console.log("[shutdown] server closed");
    process.exit(0);
  });
});

const server = app.listen(PORT, () => {
  console.log(`Meteora wrapper server listening on port ${PORT}`);
});

/**
 * POST /get_active_bin
 * Возвращает текущий binId и price (короткий аналог list_bins_around, без массива бинов)
 */
app.post("/get_active_bin", async (req, res) => {
  try {
    const { lbPair } = req.body;
    if (!lbPair) {
      return res.status(400).json({ error: "Missing lbPair" });
    }

    const poolPubkey = new PublicKey(lbPair);
    const dlmmPool = await DLMM.create(connection, poolPubkey);
    await dlmmPool.refetchStates();

    const activeBinInfo = await dlmmPool.getActiveBin();

    let activeBinId = null;
    let price = null;
    if (activeBinInfo && activeBinInfo.binId != null) {
      activeBinId =
        typeof activeBinInfo.binId === "number"
          ? activeBinInfo.binId
          : activeBinInfo.binId.toNumber();
      price = activeBinInfo.price || null;
    }

    return res.json({
      activeBinId,
      price,
    });
  } catch (err) {
    console.error("Error in /get_active_bin =>", err);
    return res.status(500).json({ error: err.message || err.toString() });
  }
});

/**
 * POST /get_pool_mints
 * Возвращает mintX, mintY, decimalsX, decimalsY для данного lbPair
 */
app.post("/get_pool_mints", async (req, res) => {
  try {
    const { lbPair } = req.body;
    if (!lbPair) {
      return res.status(400).json({ error: "Missing lbPair" });
    }

    const poolPubkey = new PublicKey(lbPair);
    const dlmmPool = await DLMM.create(connection, poolPubkey);
    await dlmmPool.refetchStates();

    await loadDecimals(dlmmPool);

    const mintXStr = dlmmPool.tokenX.publicKey.toBase58();
    const mintYStr = dlmmPool.tokenY.publicKey.toBase58();
    const decimalsX = dlmmPool.tokenX.decimals;
    const decimalsY = dlmmPool.tokenY.decimals;

    return res.json({
      mintX: mintXStr,
      mintY: mintYStr,
      decimalsX,
      decimalsY
    });
  } catch (err) {
    console.error("Error in /get_pool_mints =>", err);
    return res.status(500).json({ error: err.message || err.toString() });
  }
});


/**
 * POST /list_positions_by_user_and_lbpair
 * Возвращает активный бин + позиции юзера по данному lbPair
 * Структура ответа:
 * {
 *   "activeBin": {
 *      "binId": number,
 *      "price": string or null
 *   },
 *   "userPositions": [
 *     {
 *       "publicKey": string,
 *       "positionData": { ... }
 *     },
 *     ...
 *   ]
 * }
 */
app.post("/list_positions_by_user_and_lbpair", async (req, res) => {
  try {
    const { lbPair, userPubkey } = req.body;
    if (!lbPair || !userPubkey) {
      return res.status(400).json({ error: "Missing lbPair or userPubkey" });
    }

    const poolPubkey = new PublicKey(lbPair);
    const dlmmPool = await DLMM.create(connection, poolPubkey);
    await dlmmPool.refetchStates();

    // Получаем activeBin
    const activeBinInfo = await dlmmPool.getActiveBin();
    let activeBinObj = null;
    if (activeBinInfo && activeBinInfo.binId != null) {
      activeBinObj = {
        binId:
          typeof activeBinInfo.binId === "number"
            ? activeBinInfo.binId
            : activeBinInfo.binId.toNumber(),
        price: activeBinInfo.price || null
      };
    }

    // Ищем позиции пользователя
    const userPk = new PublicKey(userPubkey);
    const { userPositions } = await dlmmPool.getPositionsByUserAndLbPair(userPk);

    // Сериализуем для вывода
    const userPosData = userPositions.map((pos) => ({
      publicKey: pos.publicKey.toBase58(),
      positionData: pos.positionData
    }));

    return res.json({
      activeBin: activeBinObj,
      userPositions: userPosData
    });
  } catch (err) {
    console.error("Error in /list_positions_by_user_and_lbpair =>", err);
    return res.status(500).json({ error: err.message || err.toString() });
  }
});
