# Published Medicine Price Comparison / 公开药价可比较底座

This README is written for policy readers. It explains what the project is trying
to make comparable, why that is difficult, and how the policy interpretation and
data evidence are kept connected.

本 README 面向政策制定者和政策研究者。它用尽量平易近人的语言说明：这个项目要比较什么、为什么药价不能直接比较、以及系统如何把政策解释和数据证据连在一起。

## 中文版

### 这个项目想解决什么问题

各国都会公布药品价格，但这些价格经常不是同一种东西。

一个国家公布的可能是出厂价，另一个国家公布的是药房采购价，还有一个国家公布的是含税零售价。即使药品名称看起来相同，剂量、剂型、包装、税、批发加成、药房加成、报销规则也可能不同。把这些数字直接放在一张表里比较，容易得到一个看似精确、实际误导的结论。

这个项目的目标不是简单收集更多国家的价格，而是建立一个可审计的比较底座：

> 当我们说某个药在 A 国比 B 国贵或便宜时，系统必须说明：比较的是哪一种价格、这个价格在该国政策中是什么意思、是否含税、是否含批发或药房加成、是否由法规公式推导而来、以及数据是否足够可靠。

目前项目已经把七个国家接入同一个比较底座：

| 国家 | 当前状态 | 主要可比较价格基础 |
|---|---|---|
| Ireland (`IE`) | 已接入 | 药房采购价；可依法规推导出厂价 |
| Poland (`PL`) | 已接入 | 原生出厂价、批发价、零售价等多价格层次 |
| Czechia (`CZ`) | 已接入 | 原生出厂价及药房/零售价格上限 |
| Spain (`ES`) | 已接入 | 原生含税零售价；可按官方转换规则推导出厂价 |
| Italy (`IT`) | 已接入 | 原生公众零售价；可按 Class A 规则推导出厂价 |
| Portugal (`PT`) | 已接入 | 原生公众零售价；可按 Infarmed 规则推导出厂价 |
| Belgium (`BE`) | 已接入 | INAMI/RIZIV 原生出厂价 |

系统已经生成一个七国可比较索引，包含 `BE/CZ/ES/IE/IT/PL/PT`，共 94,322 行可查询的价格-lane 记录。这个索引不是简单的两两配对，而是一个跨国可比较底座。

### 为什么不能直接比较药价

举一个简化例子：

- 比利时公布 `SPB_PRICE`，政策解释为不含 VAT、不含标准批发/药房加成的出厂价。
- 爱尔兰公开的是药房采购/报销价格，但根据约束性规则，可以倒推出不含加成的出厂价。
- 西班牙公开的是含 VAT 的公众零售价，系统必须先按官方转换表扣除税和标准零售结构，才能得到一个可比较的出厂价估计。

如果把这三个原始数字直接比较，就是把出厂价、药房采购价和含税零售价混在一起。项目的设计正是为了避免这种情况。

### 核心设计：政策-数据双齿轮

系统的核心可以理解为两个齿轮同时转动。

**第一齿轮：政策解释**

每个国家的每个价格字段，都先由政策解释层判断它是什么意思。例如：

- 是否是 manufacturer price / 出厂价？
- 是否是 pharmacy purchase price / 药房采购价？
- 是否是 public retail price / 公众零售价？
- 是否含 VAT？
- 是否包含批发加成、药房加成或固定费用？
- 如果不是出厂价，是否有法律或官方方法可以推导出厂价？

这些解释不是写在代码里的猜测，而是可审计的结构化 policy interpretation。每条解释都带有来源、有效日期、信心等级和 caveats。

**第二齿轮：数据检查**

政策说某个字段可以用，还不够。数据层还要检查：

- 这个字段在实际文件中是否存在；
- 是否有足够多的非空价格；
- 价格是否为正；
- 分布是否异常；
- 货币、日期、剂型、剂量、包装是否可解析。

只有政策齿轮和数据齿轮都通过，一个价格字段才会进入比较。

### AI 在这里做什么

这个项目是 AI-native 的，但不是让 AI 随便算价格。

AI/agent 适合做政策解释：阅读国家政策文件、理解价格字段含义、判断税和加成、提出可推导公式。确定之后，这些解释被写成结构化文件。

真正的数字计算由确定性代码完成，例如：

- 每片、每毫克价格换算；
- 汇率换算；
- 从含税零售价推导出厂价；
- 剂量、剂型、包装归一化；
- INN、ATC、商品名之间的身份匹配。

一句话：AI 负责解释政策，代码负责执行计算。

### 新增一个国家时，系统如何运转

这个项目的卖点不只是“有 AI”，而是把 AI 放在正确的位置：让不同 agent 分工阅读、解释和审查政策含义，再把这些解释交给稳定的 normaliser 和计算层执行。以新增一个国家为例，系统会这样一步步工作：

1. **国家 delegate 先理解本国资料。** 它只负责这个国家：找到官方价格文件，保留原始证据，识别国家自己的字段、药品名称、剂量、包装、货币和发布时间。它不直接和别国比较，避免把跨国判断混进本国解析。
2. **Policy Intelligence 解释价格含义。** 它阅读法规、说明文件和字段定义，判断每个价格到底是出厂价、药房采购价、报销价还是公众零售价；是否含 VAT；是否包含批发或药房加成；如果不是目标价格基础，能否按法律或官方公式推导。
3. **数据齿轮反查政策判断。** 如果政策说某个字段是可用价格，数据 profile 会检查它在真实文件里是否存在、是否足够完整、价格是否合理、药品身份和剂量剂型是否能被解析。政策解释和数据表现必须相互印证。
4. **Normaliser 把本国语言翻译成共同语言。** 它把 INN、ATC、商品名、活性成分、剂量、剂型、给药路径、包装数量、货币、每片价格、每毫克价格等统一到共同字段。这里不是“猜相似药”，而是把同一个药品 presentation 放进可比较的坐标系。
5. **Derivation layer 生成可比较价格 lane。** 如果国家原生公布出厂价，系统保留 observed manufacturer-price lane。如果只公布含税零售价或药房采购价，但法规允许倒推，系统生成 derived manufacturer-price lane，并保留公式、参数、依据和信心等级。
6. **Secretariat 把国家接入 multinational substrate。** 新国家不是和每个旧国家单独配对，而是进入同一个跨国索引。查询时，系统选择同一 INN、同一剂量、同一剂型、同一给药路径、同一价格基础的 cohort。只有这样，一个国家的价格才会和其他国家真正“苹果对苹果”比较。

这就是双齿轮加 multinational delegate system 的核心：国家 delegate 负责本国事实，policy intelligence 负责语义判断，normaliser 负责共同语言，substrate 负责跨国比较。任何一步证据不足，结果就不会被包装成确定比较。

### 什么叫 multinational substrate

早期比较药价很容易走向“两两国家配对”：IE 对 PL、IE 对 CZ、PL 对 CZ……国家越多，组合越多，很快失控。

本项目现在使用的是 multinational substrate。意思是：

1. 每个国家由自己的 delegate 先完成本国解释和整理；
2. 每一行都带着自己的政策解释、数据 profile、价格类型、税/加成位置、是否 derived、药品身份、剂量、剂型、包装；
3. 查询时只取同一价格基础、同一 INN、同一剂量、同一剂型、同一路径的 cohort。

例如要比较 `atorvastatin 20 mg oral solid`，系统不会先生成所有国家两两组合，而是查找七国中满足同一可比较条件的记录。

### 一个实际例子：Belgium 加入七国比较

比利时加入时，系统不是手工写一组“比利时对爱尔兰、比利时对波兰”的规则。Belgium delegate 先读取 INAMI/RIZIV 官方 workbook，Policy Intelligence 再解释其中的 `SPB_PRICE`。这个字段被解释为原生 manufacturer price，不含 VAT，不含标准批发/药房加成。随后数据齿轮检查字段可用性，normaliser 统一 INN、剂量、剂型和每单位价格，最后把 Belgium 放进七国共同 manufacturer-price lane。

它可以和其他国家的 manufacturer-price lane 比较，但其他国家有些是原生价格，有些是政策公式推导价格。系统会保留这个区别。

七国验证中，系统用五个药物检查 Belgium 是否真的进入同一个 manufacturer-price comparison lane：

| 药物 | 可比较规格 | Belgium 相对七国中位数 |
|---|---|---:|
| atorvastatin | 20 mg oral solid | 1.38x |
| olanzapine | 10 mg oral solid | 0.80x |
| pantoprazole | 40 mg oral solid | 1.63x |
| clopidogrel | 75 mg oral solid | 0.72x |
| dapagliflozin | 10 mg oral solid | 1.16x |

这些数字的意思不是“比利时真实净价一定更高或更低”。它们表示：在公开价格、同一分子、同一剂量/剂型、同一 manufacturer-price basis 下，Belgium 在这些验证药物上的相对位置。保密折扣和 managed-entry agreements 不在本项目范围内。

### 原生价格和推导价格都可以比较吗

可以，但必须说清楚。

例如：

- Belgium、Poland、Czechia 有原生 manufacturer-price lane；
- Ireland、Spain、Italy、Portugal 的 manufacturer-price lane 是从公开价格按法规或官方方法推导出来的。

系统允许原生和推导价格进入同一个可比较 basis，但每一行都会标记 `observed` 或 `derived`，并保存推导公式、参数和法律/官方依据。这样政策读者可以看到比较结果，也可以追溯这个结果是直接公布的，还是从另一个公布价格推导出来的。

### 现在已经做了什么

项目目前已经具备以下能力：

- 保存官方来源和抓取/处理证据；
- 让国家 delegate 将本国发布资料整理成共同可读的记录；
- 为每个国家价格字段形成可审计的政策解释；
- 对每次数据快照做可用性和质量检查；
- 支持 VAT、margin、价格层次的结构化解释；
- 支持政策驱动的 derived price lane，并明确标记 observed/derived；
- 支持 INN、ATC、活性成分标签、商品名首词的身份归一；
- 支持剂量、剂型、包装、货币、每单位/每毫克价格归一；
- 建立七国 multinational lane index；
- 生成比利时七国比较报告；
- 用测试保护六国 baseline 和七国扩展。

### 这个项目不能回答什么

本项目有意不回答以下问题：

- 保密 rebate 之后的真实净价是多少；
- 医院或 payer 实际成交价是多少；
- 不同分子之间是否治疗等效；
- 某个药是否临床上更好；
- 哪个国家“应该”采用哪个价格政策。

它回答的是更窄但更可靠的问题：在公开、可追溯、可解释的价格基础上，不同国家公布的同一药品价格如何比较，以及这个比较的证据链是什么。

### 下一步

项目下一阶段会继续扩展国家，但不会以覆盖数量为第一目标。优先顺序是：能否拿到官方数据、能否解释价格含义、能否明确 VAT/margin、能否根据法律或官方方法推导可比较基础、能否稳定识别药品身份。

当前 roadmap 中，下一批高优先级国家包括 Sweden、New Zealand、Finland、Switzerland、Greece 等。美国和加拿大暂时不纳入主线，因为它们的保险、PBM、省级/联邦结构更复杂，可能需要不同的底座。

---

## English Version

### What This Project Is For

Countries publish medicine prices, but the published numbers often do not mean the same thing.

One country may publish a manufacturer price. Another may publish a pharmacy purchase price. A third may publish a VAT-inclusive public retail price. Even when the medicine name looks the same, the strength, dosage form, pack size, tax treatment, wholesale margin, pharmacy margin, reimbursement rule, and publication context may differ.

This project is not mainly a country-coverage exercise. Its purpose is to build an auditable comparison substrate:

> When we say that a medicine is more or less expensive in country A than in country B, the system must explain which price field is being compared, what that field means under national policy, whether VAT or margins are included, whether the value is observed or policy-derived, and whether the underlying data are usable.

The current substrate covers seven countries:

| Country | Current Status | Main Comparable Basis |
|---|---|---|
| Ireland (`IE`) | integrated | observed pharmacy purchase price; policy-derived manufacturer price |
| Poland (`PL`) | integrated | observed manufacturer, wholesale, public retail, and VAT-inclusive manufacturer lanes |
| Czechia (`CZ`) | integrated | observed manufacturer price and pharmacy/retail ceiling lanes |
| Spain (`ES`) | integrated | observed VAT-inclusive public retail price; policy-derived manufacturer price |
| Italy (`IT`) | integrated | observed public price; policy-derived manufacturer price |
| Portugal (`PT`) | integrated | observed public retail price; policy-derived manufacturer price |
| Belgium (`BE`) | integrated | observed INAMI/RIZIV manufacturer price |

The project now has a seven-country lane index covering `BE/CZ/ES/IE/IT/PL/PT`, with 94,322 comparable price-lane rows. It is a multinational comparison substrate, not a matrix of ad hoc country pairs.

### Why Prices Cannot Just Be Put Side by Side

A simple example:

- Belgium publishes `SPB_PRICE`, interpreted as a VAT-exclusive manufacturer price without standard wholesale or pharmacy margins.
- Ireland publishes a pharmacy purchase/reimbursement price, but legislation supports deriving a manufacturer-price basis by reversing the statutory markup.
- Spain publishes a VAT-inclusive public retail price, which must be converted through official tiers before it can be used on a manufacturer-price basis.

Putting these raw numbers side by side would mix manufacturer price, pharmacy purchase price, and VAT-inclusive retail price. The system is designed to prevent that.

### The Two-Gear Design: Policy and Data

The project works through two independent gears.

**Gear 1: Policy Interpretation**

For each country and each price field, Policy Intelligence asks:

- Is this a manufacturer price, pharmacy purchase price, public retail price, payer reimbursement price, or something else?
- Does it include VAT?
- Does it include wholesale margins, pharmacy margins, dispensing fees, or fixed fees?
- If it is not directly a manufacturer price, is there a binding law or official method that supports deriving one?

These interpretations are auditable structured records. They carry sources, effective dates, confidence levels, caveats, and derivation rules.

**Gear 2: Data Profiling**

Policy meaning is not enough. The data layer checks whether the field is actually present and usable:

- Is the field populated?
- Are prices positive?
- Is the distribution plausible?
- Are currency, dates, strength, form, pack size, and product identity usable?

A price field enters comparison only when both gears pass.

### What AI Does Here

The project is AI-native, but not in the sense that AI invents numbers.

AI agents are useful for reading policy documents and turning them into structured interpretations: what the price means, whether VAT is included, what margins apply, and whether an official derivation formula exists.

Numerical work is deterministic code:

- per-pack, per-unit, and per-mg calculation;
- currency conversion;
- VAT and margin derivation formulas;
- strength, dosage form, pack-size normalisation;
- INN, ATC, ingredient-label, and product-name identity matching.

In short: AI interprets policy; code calculates numbers.

### How the System Works When a New Country Is Added

The distinctive feature is not simply that the project uses AI. It is that AI is placed at the semantic layer, where policy interpretation is needed, and deterministic normalisers and calculation rules handle the numeric layer. When a new country is added, the system works step by step:

1. **The country delegate first understands the national source.** It works only on that country: finding the official price publication, preserving the original evidence, and identifying local fields, product names, strengths, pack sizes, currencies, and publication dates. It does not compare the country with others.
2. **Policy Intelligence interprets the price meaning.** It reads legislation, source notes, and field definitions. It decides whether each price is a manufacturer price, pharmacy purchase price, reimbursement price, public retail price, or another national concept; whether VAT is included; whether wholesale or pharmacy margins are included; and whether a target basis can be derived through law or official formula.
3. **The data gear checks the policy judgement against reality.** If policy says a field can be used, the data profile checks whether it actually exists, is sufficiently populated, has plausible positive prices, and contains product identity, strength, form, and pack information that can be parsed. Policy meaning and data behaviour must support each other.
4. **The normaliser translates national language into shared language.** It standardises INN, ATC, brand or ingredient labels, strength, dosage form, route, pack size, currency, per-unit price, and per-mg price. This is not guessing that two medicines are similar. It is placing the same medicine presentation into a common coordinate system.
5. **The derivation layer creates comparable price lanes.** If the country directly publishes a manufacturer price, the system keeps an observed manufacturer-price lane. If it publishes only a VAT-inclusive retail price or pharmacy purchase price but policy supports a reverse calculation, the system creates a derived manufacturer-price lane, with the formula, parameters, legal basis, and confidence kept attached.
6. **The Secretariat connects the country to the multinational substrate.** The new country is not manually paired with every existing country. It enters one cross-country index. A comparison then selects a cohort with the same INN, strength, dosage form, route, and price basis. That is how the system reaches an apple-to-apple comparison.

This is the operating logic of the two-gear, multinational delegate system: country delegates preserve national facts, Policy Intelligence makes semantic judgements, normalisers create a shared language, and the substrate performs cross-country comparison. If evidence is weak at any step, the system does not turn it into a confident comparison.

### What the Multinational Substrate Means

A naive system would compare every country pair separately: IE vs PL, IE vs CZ, PL vs CZ, and so on. That quickly becomes hard to maintain and easy to get wrong.

This project instead builds one multinational substrate:

1. Each country is first handled by its own delegate.
2. Each row carries its price meaning, VAT/margin position, observed/derived status, policy ID, data-profile ID, product identity, strength, dosage form, route, pack size, and normalized price.
3. Comparisons are queries over cohorts: same INN, same strength, same form, same route, and same price-lane basis.

For example, `atorvastatin 20 mg oral solid` is compared by selecting rows that meet the same identity and price-lane conditions across countries, not by manually maintaining country-pair joins.

### Example: Belgium Enters the Seven-Country Comparison

When Belgium was added, the system did not write one-off rules such as Belgium vs Ireland or Belgium vs Poland. The Belgium delegate first read the official INAMI/RIZIV workbook. Policy Intelligence then interpreted `SPB_PRICE` as an observed VAT-exclusive manufacturer price without standard wholesale or pharmacy margins. The data gear checked that the field was usable, the normaliser standardised INN, strength, form, and unit price, and Belgium then entered the shared seven-country manufacturer-price lane.

It can be compared with other manufacturer-price lanes. Some of those lanes are observed; others are derived from official formulas. The system preserves that distinction.

Five validation medicines show Belgium entering the seven-country manufacturer-price comparison lane:

| Medicine | Comparable Presentation | Belgium vs Seven-Country Median |
|---|---|---:|
| atorvastatin | 20 mg oral solid | 1.38x |
| olanzapine | 10 mg oral solid | 0.80x |
| pantoprazole | 40 mg oral solid | 1.63x |
| clopidogrel | 75 mg oral solid | 0.72x |
| dapagliflozin | 10 mg oral solid | 1.16x |

These are not net-price claims. They are published-price comparisons on a controlled manufacturer-price basis, with confidential rebates and managed-entry agreements explicitly out of scope.

### Observed and Derived Prices

Observed and derived values can be compared, but only when the evidence is explicit.

For example:

- Belgium, Poland, and Czechia have observed manufacturer-price lanes.
- Ireland, Spain, Italy, and Portugal have manufacturer-price lanes derived from published prices using structured policy rules.

The substrate allows these rows into the same comparison basis only when their final price meaning aligns. It keeps the observed/derived flag, the derivation formula, parameters, legal basis, and caveats with each row.

### What Has Been Built

The project currently supports:

- official source preservation and processing evidence;
- country delegates that translate national publications into shared records;
- auditable policy interpretations for price fields;
- data profiles for snapshot quality and usability;
- explicit VAT, margin, and price-stage semantics;
- policy-driven derived price lanes, with observed/derived status kept explicit;
- INN, ATC, ingredient-label, and product-name identity resolution;
- strength, dosage-form, pack-size, currency, and per-mg normalization;
- a seven-country multinational lane index;
- a Belgium seven-country comparison update;
- regression tests protecting the six-country baseline and Belgium expansion.

### What This Project Does Not Claim

The substrate does not estimate:

- confidential net prices after rebates;
- hospital tender prices or private transaction prices;
- clinical or therapeutic equivalence across different molecules;
- whether one policy is better than another.

It answers a narrower and more reliable question: given published and auditable price evidence, how do comparable prices for the same medicine differ across countries, and what evidence supports the comparison?

### Next Steps

The next phase is country expansion, but coverage is not the main goal. A country should enter only when the source is official, the price meaning can be interpreted, VAT and margins can be explained, derivations are legally or officially grounded, and product identity can be normalized.

High-priority future candidates include Sweden, New Zealand, Finland, Switzerland, and Greece. The United States and Canada are deferred because their insurance, PBM, provincial/federal, and rebate structures likely require a different substrate.
