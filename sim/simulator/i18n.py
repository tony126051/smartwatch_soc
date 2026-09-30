"""
Internationalization (i18n) Support for Smartwatch SoC Simulator
Supports:
  - zh-TW: Traditional Chinese (繁體中文) [Default]
  - en: English
  - zh-CN: Simplified Chinese (简体中文)
  - ja: Japanese (日本語)
"""

from typing import Dict, Any

LANGUAGES = {
    "zh-TW": "繁體中文",
    "en": "English",
    "zh-CN": "简体中文",
    "ja": "日本語"
}

# Normalization map for CLI inputs
LANG_ALIASES = {
    "zh-tw": "zh-TW",
    "zhtw": "zh-TW",
    "zh_tw": "zh-TW",
    "tw": "zh-TW",
    "traditional": "zh-TW",
    "en": "en",
    "en-us": "en",
    "english": "en",
    "zh-cn": "zh-CN",
    "zhcn": "zh-CN",
    "zh_cn": "zh-CN",
    "cn": "zh-CN",
    "simplified": "zh-CN",
    "ja": "ja",
    "jp": "ja",
    "japanese": "ja"
}

MESSAGES: Dict[str, Dict[str, str]] = {
    "zh-TW": {
        # Banner & General
        "banner_title": "Smartwatch SoC 視覺化互動模擬器與硬體除錯器",
        "banner_arch": "架構: 32-bit RISC-V (PicoRV32) + AFE + VAD + KWS DS-CNN NPU",
        "banner_specs": "系統時脈: 12.288 MHz | 功耗模型: <20 μW 待機 | 晶片內 16KB SRAM",
        "banner_prompt": "輸入 'help' 查看指令清單，'run' 執行，'step' 單步執行，'lang' 切換語言。\n",
        "unknown_cmd": "未知指令: '{cmd}'。輸入 'help' 獲取協助。",
        "exiting": "模擬器已結束退出。",
        "bp_set": "中斷點已設定於 0x{addr:08x}",
        "bp_list": "目前中斷點清單:",
        "bp_removed": "已移除中斷點 0x{addr:08x}",
        "bp_cleared": "所有中斷點已清除。",
        "bp_hit": "於 {steps} 週期後觸發中斷點 0x{addr:08x}。",
        "sleep_hit": "CPU 於 {steps} 週期後進入低功耗待機休眠 (WFI)。[LED = 0x{led:02x}]",
        "trapped": "CPU 於 0x{addr:08x} 陷入異常 (Trapped)！停止執行。",
        "run_done": "已完成 {steps} 週期。PC = 0x{addr:08x}",
        "reset_done": "SoC 全系統硬體重設完成。",
        "feed_done": "已向音訊前端麥克風注入: {type}",
        "lang_switched": "語言已切換至: {name} ({code})",
        "lang_list": "支援的語言代碼: zh-TW (繁體中文), en (English), zh-CN (简体中文), ja (日本語)",
        
        # CLI Help
        "help_title": "可用命令清單:",
        "cmd_step_desc": "執行 N 條指令 (預設 1)",
        "cmd_run_desc": "持續執行直至中斷點、異常或休眠 (預設 100,000 週期)",
        "cmd_break_desc": "於指定位址設定中斷點 (例: break 0x10, break 0x48)",
        "cmd_delete_desc": "移除指定中斷點或清除所有中斷點",
        "cmd_regs_desc": "傾印所有 32 顆 RISC-V 通用暫存器數值",
        "cmd_mem_desc": "檢視記憶體內容 (例: mem 0x10000000 16)",
        "cmd_status_desc": "顯示 SoC 周邊硬體即時狀態 (AFE, VAD, NPU, LED, CPU)",
        "cmd_feed_desc": "向麥克風注入測試音訊 (speech | tone | silence)",
        "cmd_power_desc": "顯示功耗分析、累積能耗與電池壽命估計",
        "cmd_lang_desc": "切換語言介面 (例: lang en, lang zh-tw, lang ja)",
        "cmd_reset_desc": "重設 SoC 所有暫存器與硬體周邊",
        "cmd_quit_desc": "結束模擬器連線",
        
        # Regression
        "reg_title": "  [回歸測試套件] Smartwatch SoC 子系統與全晶片功能驗證",
        "reg_test1": "[測試 1/5] 驗證 RISC-V RV32I 處理器核心與記憶體子系統...",
        "reg_test1_pass": "  [通過] RISC-V RV32I 算術與自訂指令 (waitirq) 100% 正確",
        "reg_test2": "[測試 2/5] 驗證音訊前端 (3 階 CIC 降頻濾波器與 FIFO)...",
        "reg_test2_pass": "  [通過] CIC 濾波器降頻 PDM 串流 -> FIFO 樣本數: {count}, 樣本值 = {sample}",
        "reg_test3": "[測試 3/5] 驗證第一級硬體語音活動偵測器 (Hardware VAD Core)...",
        "reg_test3_pass1": "  [通過] 硬體 VAD 短時能量累加計算 100% 位元精確！",
        "reg_test3_pass2": "  [通過] 上升沿喚醒中斷 (irq_vad_wakeup) 於第 2 幀成功觸發！",
        "reg_test4": "[測試 4/5] 驗證第二級 KWS NPU 加速器與 INT8 量化推論...",
        "reg_test4_pass1": "  [通過] NPU DS-CNN 推論結果與 Python 黃金模型 100% 位元精確！",
        "reg_test4_latency": "  [通過] 硬體執行延遲: {cycles} 週期 ({ms:.2f} ms @ 12.288MHz)",
        "reg_test4_scores": "  [通過] 分類推論得分: Class 0 (背景雜音) = {s0}, Class 1 (喚醒詞) = {s1}",
        "reg_test5": "[測試 5/5] 驗證全系統整合與實際 RISC-V 韌體執行流程...",
        "reg_test5_s1": "  [通過] 階段 1: CPU 開機 -> 配置 AFE/VAD -> 進入待機休眠 (LED = 0x04)",
        "reg_test5_s2": "  [通過] 階段 2: 偵測到語音串流 -> 觸發 VAD 喚醒中斷 -> CPU 執行 ISR",
        "reg_test5_s3": "  [通過] 階段 3: 載入語音特徵矩陣 -> 完成 NPU 硬體推論 -> LED = 0x55",
        "reg_summary_title": "  Smartwatch SoC PPA、延遲與動態功耗預估摘要",
        "reg_all_pass": "  >>> 全數 5 項回歸測試通過 (100% 位元精確驗證成功) <<<",
    },
    
    "en": {
        # Banner & General
        "banner_title": "Smartwatch SoC Interactive Simulator & Hardware Debugger",
        "banner_arch": "Architecture: 32-bit RISC-V (PicoRV32) + AFE + VAD + KWS DS-CNN NPU",
        "banner_specs": "System Clock: 12.288 MHz | Power Model: <20 uW Standby | On-Chip 16KB SRAM",
        "banner_prompt": "Type 'help' for commands, 'run' to execute, 'step' to step, 'lang' to change language.\n",
        "unknown_cmd": "Unknown command: '{cmd}'. Type 'help' for assistance.",
        "exiting": "Simulator session ended.",
        "bp_set": "Breakpoint set at 0x{addr:08x}",
        "bp_list": "Active breakpoints:",
        "bp_removed": "Breakpoint removed from 0x{addr:08x}",
        "bp_cleared": "All breakpoints cleared.",
        "bp_hit": "Hit Breakpoint at 0x{addr:08x} after {steps} cycles.",
        "sleep_hit": "CPU entered Low-Power Standby Sleep (WFI) after {steps} cycles. [LED = 0x{led:02x}]",
        "trapped": "CPU Trapped at 0x{addr:08x} after {steps} cycles! Halting.",
        "run_done": "Completed {steps} cycles. PC = 0x{addr:08x}",
        "reset_done": "SoC Full-System Hardware Reset Complete.",
        "feed_done": "Audio stream fed into microphone front-end: {type}",
        "lang_switched": "Language switched to: {name} ({code})",
        "lang_list": "Supported language codes: zh-TW (Traditional Chinese), en (English), zh-CN (Simplified Chinese), ja (Japanese)",
        
        # CLI Help
        "help_title": "Available Commands:",
        "cmd_step_desc": "Execute N instructions (default 1)",
        "cmd_run_desc": "Run until next breakpoint, trap, or sleep (default 100,000 cycles)",
        "cmd_break_desc": "Set breakpoint at address (e.g. break 0x10, break 0x48)",
        "cmd_delete_desc": "Remove breakpoint or all breakpoints",
        "cmd_regs_desc": "Dump all 32 RISC-V CPU general-purpose registers",
        "cmd_mem_desc": "Inspect memory (e.g. mem 0x10000000 16)",
        "cmd_status_desc": "Show SoC peripheral status (AFE, VAD, NPU, LEDs, CPU)",
        "cmd_feed_desc": "Inject audio into microphone front-end (speech | tone | silence)",
        "cmd_power_desc": "Display power profile, energy, and battery life projection",
        "cmd_lang_desc": "Switch language (e.g. lang en, lang zh-tw, lang ja)",
        "cmd_reset_desc": "Reset all SoC registers and peripherals",
        "cmd_quit_desc": "Exit simulation session",
        
        # Regression
        "reg_title": "  [Regression Test Suite] Smartwatch SoC Subsystems & Full-Chip Verification",
        "reg_test1": "[Test 1/5] Verifying RISC-V RV32I Processor Core & Memory Subsystem...",
        "reg_test1_pass": "  [PASS] RISC-V RV32I Arithmetic & waitirq Instructions 100% OK",
        "reg_test2": "[Test 2/5] Verifying Audio Front-End (3rd-Order CIC Decimator & FIFO)...",
        "reg_test2_pass": "  [PASS] CIC Decimator filtered PDM stream -> FIFO Sample count: {count}, Sample = {sample}",
        "reg_test3": "[Test 3/5] Verifying Hardware Voice Activity Detector (VAD Core)...",
        "reg_test3_pass1": "  [PASS] Hardware VAD Short-Time Energy Accumulation 100% Bit-True!",
        "reg_test3_pass2": "  [PASS] Rising-edge Wakeup IRQ successfully asserted on Frame 2!",
        "reg_test4": "[Test 4/5] Verifying Level-2 KWS NPU Accelerator & Quantization...",
        "reg_test4_pass1": "  [PASS] NPU DS-CNN Inference Matched Golden Reference 100% Bit-True!",
        "reg_test4_latency": "  [PASS] Execution Latency: {cycles} cycles ({ms:.2f} ms @ 12.288MHz)",
        "reg_test4_scores": "  [PASS] Classification Scores: Class 0 (Noise) = {s0}, Class 1 (Keyword) = {s1}",
        "reg_test5": "[Test 5/5] Verifying Full SoC Integration with Real RISC-V Firmware...",
        "reg_test5_s1": "  [PASS] Stage 1: CPU Booted -> Configured AFE/VAD -> Entered Standby Sleep (LED = 0x04)",
        "reg_test5_s2": "  [PASS] Stage 2: Voice Stream Detected -> VAD Wakeup IRQ Triggered -> CPU Serviced ISR",
        "reg_test5_s3": "  [PASS] Stage 3: Feature Window Loaded -> NPU Inference Executed -> LED = 0x55",
        "reg_summary_title": "  Smartwatch SoC PPA, Latency & Power Estimation Summary",
        "reg_all_pass": "  >>> ALL 5 REGRESSION TESTS PASSED (100% BIT-TRUE VERIFIED) <<<",
    },

    "zh-CN": {
        # Banner & General
        "banner_title": "Smartwatch SoC 可视化交互模拟器与硬件调试器",
        "banner_arch": "架构: 32-bit RISC-V (PicoRV32) + AFE + VAD + KWS DS-CNN NPU",
        "banner_specs": "系统时钟: 12.288 MHz | 功耗模型: <20 μW 待机 | 片上 16KB SRAM",
        "banner_prompt": "输入 'help' 查看命令列表，'run' 运行，'step' 单步，'lang' 切换语言。\n",
        "unknown_cmd": "未知命令: '{cmd}'。输入 'help' 获取帮助。",
        "exiting": "模拟器已结束退出。",
        "bp_set": "断点已设置于 0x{addr:08x}",
        "bp_list": "当前断点列表:",
        "bp_removed": "已移除断点 0x{addr:08x}",
        "bp_cleared": "所有断点已清除。",
        "bp_hit": "于 {steps} 周期后命中断点 0x{addr:08x}。",
        "sleep_hit": "CPU 于 {steps} 周期后进入低功耗待机休眠 (WFI)。[LED = 0x{led:02x}]",
        "trapped": "CPU 于 0x{addr:08x} 陷入异常 (Trapped)！停止运行。",
        "run_done": "已完成 {steps} 周期。PC = 0x{addr:08x}",
        "reset_done": "SoC 全系统硬件复位完成。",
        "feed_done": "已向麦克风前端注入测试音频: {type}",
        "lang_switched": "语言已切换至: {name} ({code})",
        "lang_list": "支持的语言代码: zh-TW (繁体中文), en (English), zh-CN (简体中文), ja (日本語)",
        
        # CLI Help
        "help_title": "可用命令列表:",
        "cmd_step_desc": "执行 N 条指令 (默认 1)",
        "cmd_run_desc": "持续执行直到断点、异常或休眠 (默认 100,000 周期)",
        "cmd_break_desc": "在指定地址设置断点 (例: break 0x10, break 0x48)",
        "cmd_delete_desc": "删除指定断点或清除全部断点",
        "cmd_regs_desc": "转储所有 32 个 RISC-V 通用寄存器",
        "cmd_mem_desc": "检查内存内容 (例: mem 0x10000000 16)",
        "cmd_status_desc": "显示 SoC 外设硬件实时状态 (AFE, VAD, NPU, LED, CPU)",
        "cmd_feed_desc": "向麦克风注入测试音频 (speech | tone | silence)",
        "cmd_power_desc": "显示功耗分析、能耗与电池寿命预测",
        "cmd_lang_desc": "切换语言界面 (例: lang en, lang zh-cn, lang ja)",
        "cmd_reset_desc": "复位 SoC 全部寄存器与外设",
        "cmd_quit_desc": "退出模拟会话",
        
        # Regression
        "reg_title": "  [回归测试套件] Smartwatch SoC 子系统与全芯片功能验证",
        "reg_test1": "[测试 1/5] 验证 RISC-V RV32I 处理器核心与内存子系统...",
        "reg_test1_pass": "  [通过] RISC-V RV32I 算术与自定义指令 (waitirq) 100% 正确",
        "reg_test2": "[测试 2/5] 验证音频前端 (3 阶 CIC 降频滤波器与 FIFO)...",
        "reg_test2_pass": "  [通过] CIC 滤波器降频 PDM 流 -> FIFO 样本数: {count}, 样本值 = {sample}",
        "reg_test3": "[测试 3/5] 验证第一级硬件语音活动检测器 (Hardware VAD Core)...",
        "reg_test3_pass1": "  [通过] 硬件 VAD 短时能量累加计算 100% 比特精确！",
        "reg_test3_pass2": "  [通过] 上升沿唤醒中断 (irq_vad_wakeup) 于第 2 帧成功触发！",
        "reg_test4": "[测试 4/5] 验证第二级 KWS NPU 加速器与 INT8 量化推理...",
        "reg_test4_pass1": "  [通过] NPU DS-CNN 推理结果与 Python 黄金模型 100% 比特精确！",
        "reg_test4_latency": "  [通过] 硬件执行延迟: {cycles} 周期 ({ms:.2f} ms @ 12.288MHz)",
        "reg_test4_scores": "  [通过] 分类推理得分: Class 0 (背景噪声) = {s0}, Class 1 (唤醒词) = {s1}",
        "reg_test5": "[测试 5/5] 验证全系统集成与实际 RISC-V 固件执行流程...",
        "reg_test5_s1": "  [通过] 阶段 1: CPU 开机 -> 配置 AFE/VAD -> 进入待机休眠 (LED = 0x04)",
        "reg_test5_s2": "  [通过] 阶段 2: 检测到语音流 -> 触发 VAD 唤醒中断 -> CPU 执行 ISR",
        "reg_test5_s3": "  [通过] 阶段 3: 加载语音特征矩阵 -> 完成 NPU 硬件推理 -> LED = 0x55",
        "reg_summary_title": "  Smartwatch SoC PPA、延迟与动态功耗预估摘要",
        "reg_all_pass": "  >>> 全部 5 项回归测试通过 (100% 比特精确验证成功) <<<",
    },

    "ja": {
        # Banner & General
        "banner_title": "Smartwatch SoC インタラクティブシミュレータ & ハードウェアデバッガ",
        "banner_arch": "アーキテクチャ: 32-bit RISC-V (PicoRV32) + AFE + VAD + KWS DS-CNN NPU",
        "banner_specs": "システムクロック: 12.288 MHz | 待機電力モデル: <20 μW | オンチップ 16KB SRAM",
        "banner_prompt": "'help' でコマンド一覧、'run' で実行、'step' でステップ実行、'lang' で言語切替。\n",
        "unknown_cmd": "不明なコマンド: '{cmd}'。'help' を参照してください。",
        "exiting": "シミュレータセッションを終了しました。",
        "bp_set": "ブレークポイントを 0x{addr:08x} に設定しました",
        "bp_list": "有効なブレークポイント:",
        "bp_removed": "0x{addr:08x} のブレークポイントを解除しました",
        "bp_cleared": "すべてのブレークポイントをクリアしました。",
        "bp_hit": "{steps} サイクル後にブレークポイント 0x{addr:08x} に到達しました。",
        "sleep_hit": "CPU が {steps} サイクル後に省電力待機スリープ (WFI) に入りました。[LED = 0x{led:02x}]",
        "trapped": "CPU が 0x{addr:08x} でトラップしました！停止します。",
        "run_done": "{steps} サイクル完了。PC = 0x{addr:08x}",
        "reset_done": "SoC 全システムハードウェアリセット完了。",
        "feed_done": "マイク入力にテスト音声を注入しました: {type}",
        "lang_switched": "言語を切り替えました: {name} ({code})",
        "lang_list": "サポートされている言語: zh-TW (繁体中国語), en (英語), zh-CN (簡体中国語), ja (日本語)",
        
        # CLI Help
        "help_title": "使用可能なコマンド一覧:",
        "cmd_step_desc": "N 個の命令を実行 (デフォルト 1)",
        "cmd_run_desc": "ブレークポイント・トラップ・スリープまで実行 (デフォルト 100,000 サイクル)",
        "cmd_break_desc": "指定アドレスにブレークポイントを設定 (例: break 0x10, break 0x48)",
        "cmd_delete_desc": "ブレークポイントを解除または全クリア",
        "cmd_regs_desc": "RISC-V CPU の 32 本の汎用レジスタを表示",
        "cmd_mem_desc": "メモリ内容を表示 (例: mem 0x10000000 16)",
        "cmd_status_desc": "SoC 周辺回路のリアルタイム状態を表示 (AFE, VAD, NPU, LED, CPU)",
        "cmd_feed_desc": "マイクにテスト音声を注入 (speech | tone | silence)",
        "cmd_power_desc": "消費電力・累積エネルギー・バッテリー駆動時間予測を表示",
        "cmd_lang_desc": "表示言語を切り替え (例: lang en, lang ja, lang zh-tw)",
        "cmd_reset_desc": "SoC 全レジスタと周辺回路をリセット",
        "cmd_quit_desc": "シミュレータを終了",
        
        # Regression
        "reg_title": "  [回帰テストスイート] Smartwatch SoC サブシステム & 全チップ検証",
        "reg_test1": "[テスト 1/5] RISC-V RV32I プロセッサコアとメモリの検証...",
        "reg_test1_pass": "  [合格] RISC-V RV32I 演算およびカスタム命令 (waitirq) 100% 正常",
        "reg_test2": "[テスト 2/5] オーディオフロントエンド (3次 CIC フィルタ & FIFO) の検証...",
        "reg_test2_pass": "  [合格] CIC フィルタで PDM 間引き -> FIFO サンプル数: {count}, サンプル値 = {sample}",
        "reg_test3": "[テスト 3/5] ハードウェア音声活動検出器 (VAD Core) の検証...",
        "reg_test3_pass1": "  [合格] ハードウェア VAD 短時間エネルギー累積計算 100% ビット完全一致！",
        "reg_test3_pass2": "  [合格] 立上がりウェイクアップ割込み (irq_vad_wakeup) が第 2 フレームで発火！",
        "reg_test4": "[テスト 4/5] 第2段 KWS NPU アクセラレータ & INT8 量子化推論の検証...",
        "reg_test4_pass1": "  [合格] NPU DS-CNN 推論結果がゴールデンモデルと 100% ビット完全一致！",
        "reg_test4_latency": "  [合格] ハードウェア実行遅延: {cycles} サイクル ({ms:.2f} ms @ 12.288MHz)",
        "reg_test4_scores": "  [合格] 分類スコア: Class 0 (背景ノイズ) = {s0}, Class 1 (ウェイクワード) = {s1}",
        "reg_test5": "[テスト 5/5] 全システム統合と RISC-V ファームウェア実行シーケンスの検証...",
        "reg_test5_s1": "  [合格] フェーズ 1: CPU 起動 -> AFE/VAD 設定 -> スタンバイ待機 (LED = 0x04)",
        "reg_test5_s2": "  [合格] フェーズ 2: 音声検出 -> VAD 割込み発火 -> CPU が ISR 処理",
        "reg_test5_s3": "  [合格] フェーズ 3: 音声特徴行列読込 -> NPU 推論実行 -> LED = 0x55",
        "reg_summary_title": "  Smartwatch SoC PPA・レイテンシ・動的電力推定サマリー",
        "reg_all_pass": "  >>> 全 5 項目の回帰テストに合格 (100% ビット完全一致検証) <<<",
    }
}

_current_lang = "zh-TW"

def set_language(lang_code: str) -> str:
    global _current_lang
    normalized = LANG_ALIASES.get(lang_code.lower().strip(), None)
    if normalized and normalized in MESSAGES:
        _current_lang = normalized
        return _current_lang
    return _current_lang

def get_current_language() -> str:
    return _current_lang

def tr(key: str, lang: str = None, **kwargs) -> str:
    use_lang = lang if lang and lang in MESSAGES else _current_lang
    text = MESSAGES.get(use_lang, {}).get(key, MESSAGES["en"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
