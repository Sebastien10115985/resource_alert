# 资源类型 → 平台入口：实测验证报告

> 实测时间：2026-11-24（第一批），2026-11-25 追加第二批国资委认定产权交易机构。方法：对每个平台做直接 HTTP 访问（长超时 45s）+ 浏览器渲染读取 + 前端 API 逆向，判断"能否程序化抓到真实挂牌数据"。
> 核心结论：**"能打开"≠"能抓到数据"**。你给的清单方向正确，但可抓取性差异极大——有的接口完全开放，有的必须登录，有的动态渲染且有验证码。

---

## 一、实测总览（19个平台）

| 平台 | 清单定位 | 实测可抓性 | 真实数据 | 关键限制 |
|---|---|---|---|---|
| **全国土地二级市场 market.mnr.gov.cn** | 存量建设用地转让/出租 | ⭐⭐⭐ 完全开放API | 转让15 + 求购12 + 成交公示15 + 热门450 | 无登录无验证码，接口直连 |
| **矿业权市场 ky.mnr.gov.cn** | 探矿权/采矿权出让+转让 | ⭐⭐⭐ 静态HTML全可抓 | **287条**（含转让公示99条） | 静态页+分页，极稳定 |
| **全国公共资源交易 ggzy.gov.cn** | 土地出让/国有产权 | ⭐⭐ 详情页可抓，列表受限 | 样本14条（土地出让/国有产权真实公告） | 列表JS渲染，API有验证码(829)+限流(800) |
| **e交易 ejy365.com** | 国有产权/厂房 | ⭐⭐⭐ 可抓 | 前日已采1232条 | 列表静态，详情静态，稳定 |
| 中国土地市场网 landchina.com | 土地一级市场出让 | ⭐ 首页可开 | 首页仅框架 | 查询需交互，未抓到列表 |
| 江苏农村产权 jtzc.jssny.com.cn | 四荒地/农村资产 | ⭐ 域名已变更 | 公开页仅政策文件 | **原jsnc.gov.cn已失效**；挂牌明细在会员端(app3.jssny.com.cn)需登录 |
| 成都农村产权 cdaee.com | 闲置资产超市 | ⭐ 首页可开 | 仅累计成交统计(16.5万宗/2518亿) | "正在挂牌数"显示"-"，明细需登录 |
| 武汉农村产权 whnccq.com | 农村产权 | ⭐ 空壳 | 无 | SPA仅878字节 |
| 天津农村产权 tjnjs.com | 农村产权 | ⭐ 空壳 | 无 | SPA仅1.7KB |
| 南方林业产权 smfor.org.cn | 林权 | ⭐ 空壳 | 无 | SPA骨架屏 |
| 华东林业产权 hdlqjy.com | 林权 | ✗ 502 | 无 | 站点网关错误 |
| 北京产权交易所 cbex.com.cn | 国资/土地二级 | ✗ 521 | 无 | CDN拦截 |
| 上海联合产权 suaee.com | 长三角国资 | ⭐ SPA | 未定位到公开列表 | 项目列表路径404 |
| 北交所诉讼资产 otc.cbex.com | 诉讼资产 | ✗ 连接失败 | 无 | 网络不可达 |
| **人民法院诉讼资产网 rmfysszc.gov.cn** | 司法拍卖房产/车/土地 | ⭐⭐⭐ 可抓（已接入） | 实测一轮 60 条当日公告，已入库 | 列表走 www1 域 POST /News/Handler.aspx；详情静态页可直连，含起拍/评估/保证金/面积；无验证码 |
| **武汉光谷 ovupre.com** | 国有资产/增资/租赁 | ⭐⭐⭐ 可抓（已接入） | 实测 65 条入库 | GET `/index/new_getxxmm.html` 返回 JSON，字段 XMMC/XMBH/ZRDJ/KSRQ/JSRQ |
| **深圳联合产权 sotcbb.com** | 公有产权/房产/设备 | ⭐⭐⭐ 可抓（已接入） | 实测 60 条入库 | POST `/api/v1/sotcbb/local/project/list`，字段全（价格/起止日/地区/项目编号） |
| **厦门产权 xemas.com.cn** | 资产出租/转让/股权 | ⭐⭐⭐ 可抓（已接入） | 实测 60 条入库 | POST `/cms/article/query`，按 `categorys` 分类树查询 |
| **青海产权 qhcqjy.com** | 房产/设备/股权/招租 | ⭐⭐ 可抓（已接入） | 实测 10 条入库 | `/item.do?para=viewlist` GBK 列表，详情需逐页解析 |
| **贵州阳光 prechina.net** | 资产/房产/设备 | ⭐⭐⭐ 可抓（已接入） | 实测 6 条入库 | `/project/` 静态列表，项目编号与挂牌价在 span 中 |
| **全国产权门户 cspea.com.cn** | 全国 36 家交易所挂牌项目 | ⭐⭐⭐ 可抓（已接入） | 实测 40 条入库，33 条含评估价 | `/list?c=C01..C06&s=A02,A03` SSR 内嵌 `listData` JSON；详情页内嵌 `projectDetailData`（评估价、来源交易所、源站链接）；一个源覆盖全国 |

> 第二批完整 36 家名单与逐站核验结论见工作区 `output/sasac_property_exchanges.md`。
| 全国企业破产重整 pccz.court.gov.cn | 破产财产 | ⭐⭐ 接口可用(前日验证) | 接口POST searchKey/gjsslb | 全文匹配易混外地案号 |
| 阿里拍卖破产强清 susong.taobao.com | 实际出价 | ⭐⭐ WebFetch可读 | 详情页渲染可读 | 直连跳登录；mtop 接口需 token 签名见 §六 |
| 京东拍卖破产强清 auction.jd.com | 实际出价 | ⭐ 空壳 | 无 | 仅157字节 |
| 南京公共资源 njggzy.nanjing.gov.cn | 地方产权 | ⭐ nginx默认页 | 无 | 根路径非业务入口 |
| 中国土地市场网 landchina.mnr.gov.cn | — | ✗ 超时 | 无 | 45s超时 |

可抓性分级：⭐⭐⭐=接口/静态页直连可批量抓；⭐⭐=部分可抓或需渲染；⭐=仅框架/需登录；✗=不可访问。

---

## 二、三个真正能抓到"真东西"的平台（附实测数据）

### 1. 全国土地二级市场交易服务平台 — 本次最大发现
前端 app.js 逆向出公开 API，**无需登录、无验证码**，直接返回结构化 JSON（含面积、价格、地区、用途、年限）：

- 接口前缀：`https://market.mnr.gov.cn/api/epf-landweb/...`
- `/tsell/getTransfer` 转让信息 15 条、`/tpurchase/getIndexTPurchaseList` 求购 12 条、`/tlandSearch/getListPopular` 热门 450 条、`/landweb/transtarget/transNoticeOrResultList` 成交公示
- 实测样本：长沙县10亩工业用地+3600㎡房产 **580万**；哈尔滨双城区3万㎡工业用地 **3500万**；喀什81.6亩商住用地 1.33亿

### 2. 矿业权市场 — 最稳定
静态 HTML + `index_N.html` 分页，采集脚本稳定拿到 287 条：
- 探矿权出让50、采矿权出让44、**探矿权转让公示50、采矿权转让公示49**（矿主出手线索）、出让结果94
- 样本：赤峰翁牛特旗铅锌矿勘探转让、河南嵩县金矿详查转让、建德市砂岩矿采矿权转让

### 3. 全国公共资源交易平台 — 详情页可抓
- 列表页 JS 渲染，数据接口 `/information/pubTradingInfo/getTradList` 带验证码机制（code 829）和限流（code 800），不硬闯
- 详情页为静态 HTML，14 条样本全部直连成功；渲染读取可见大量当日国有产权/土地出让公告（商铺竞价、物业招租、土地成交）

---

## 三、对你清单的修正与补充

1. **江苏农交所域名已变更**：`jsnc.gov.cn` → `jtzc.jssny.com.cn`（官网挂通知）。挂牌明细在会员端 `app3.jssny.com.cn`，需登录。
2. **农村产权/林权平台普遍"公开页只有统计和政策，明细要登录"**——成都、江苏、武汉、天津、南方林权实测均如此。这类平台适合人工查，不适合纯公开抓取。
3. **北交所(521)、华东林权(502)、上海联交所(项目列表404)** 当前直连不稳定。
4. **你清单里"e交易全国6000多家机构、厂房量最大"的判断正确**——前日已从该站采到1232条在报名标的。

---

## 四、性价比/机会筛选的现实提醒

- **国资产权交易（e交易、公共资源、北交所）挂牌价≈评估价**，不能贱卖，几乎无"捡漏"；机会在二次挂牌、流拍降价。
- **土地二级市场是真有折价的**（个人/企业急转），但要注意：权属是出让还是划拨、能否分割过户、有无抵押查封在租、规划用途、环保/矿坑治理义务。
- **矿业权转让公示只是"意向线索"**，不是标准挂牌，需私下联系+尽调，且矿坑往往附生态修复义务。

---

## 五、产出文件

- `platform_probe.json` / `platform_probe.csv`：19个平台探测原始数据
- `ky_notices.csv`：287条矿业权公告/转让公示
- `market_mnr_listings.csv`：44条土地二级市场转让/求购/成交数据
- `ggzy_samples.csv`：14条公共资源交易平台真实公告样本（详情页可达）
- 采集脚本：`probe_platforms.py`、`collect_ky.py`、`collect_market_mnr.py`、`ggzy_samples.py`

---

## 六、补充实测（2026-11-25）：阿里拍卖与采集调度

### 阿里开放平台司法拍卖 API — 文档在但申请不到
- 官方确有免费、免用户授权的司法拍卖接口：`taobao.auction.gov.get.latestbid`（含评估价 consult_price / 起拍价 init_price / 当前出价）、`get.auction.info`（含第几次拍卖、竞买结果、报名/出价次数、公告全文、优先购买人）、`get.auction.status`、`data.realtime.get`。
- 但当前开放平台创建应用的业务类型只有"淘宝购物小程序/商家经营工具/小程序插件/阿里生态API开放/内容创作工具"，官方类目入驻规则（2026-02 更新）也不含"司法拍卖"或公共数据类——进入"阿里生态API开放"后类目只有闲鱼/饿了么等，**无拍卖入口**；叠加个人实名认证不满足应用软件开发商的企业资质要求。
- 结论：这些接口面向早年已接入的特定合作方，新开发者自助注册拿不到权限。**不接 API，改走诉讼资产网静态页**。

### 人民法院诉讼资产网 rmfysszc.gov.cn — 已接入
- 列表接口：`POST https://www1.rmfysszc.gov.cn/News/Handler.aspx`，参数 `search/fid1/fid2/fid3/page/include`，返回 JSON（`html` 列表行 + `page` 分页）；**必须 www1 域**，www 主域同一路径返回错误页。
- 每行含公告标题（`title` 属性）、法院名、发布日期（如 2026.11.25）、详情页链接；每页 21 条，按日期倒序，最新页即当日公告——适合每日增量。
- 详情页：`https://www.rmfysszc.gov.cn/statichtml/rm_xmdetail/{id}.shtml` 静态页直连，可提取起拍价/评估价/保证金/面积/权证号/用途；注意数字夹空格（"5 00 0"）与"万元/元"混用，需归一化。评估价覆盖率约 1/6，起拍价约 6/10。
- 已实现 `collectors/rmfysszc.py`（open 组，间隔 0.4s），只保留 `fresh_days`（7 天）内公告，标题识别资产类型；实测一轮抓 60 条当日公告并全部入库，有评估价的标的折扣 0.55~0.8，v2 性价比分能拉开到 85。

### 阿里拍卖 sf/susong.taobao.com — 不可自动化采集
- `sf.taobao.com` / `zc.taobao.com` 首页 HTTP 200、约 274KB，但纯前端 Rax 渲染，静态 HTML 无标的列表。
- `susong.taobao.com` 标题可见（"破产甩卖-阿里资产…"），数据同样前端渲染。
- 老版 `item_list.htm` 是 GBK 静态页，但 `<div class="sf-item-list">` 列表容器为空；页面里出现的"33万/57万/101万"是**价格筛选项**，不是标的价，不可误当数据。
- 数据接口 `mtop.taobao.datafront.invoke.auctionwalle` 直连返回 `FAIL_SYS_TOKEN_EMPTY::令牌为空`——必须先取页面 cookie 再按阿里规则签名。按合规原则**不做 token 伪造/签名绕过**，不接入自动采集。

### 全国公共资源交易 ggzy.gov.cn — 站点改版，列表仍受限
- 列表页路径已改版：`/information/dealList.html` → `/deal/dealList.html`。
- 列表接口仍是 `POST /information/pubTradingInfo/getTradList`，带验证码（code 829）+ 限流（800/801）+ `X-Pass-Token` 校验；直连返回 404 风控页，**不硬闯**。
- 详情页 `/information/deal/html/...` 仍是静态 HTML，直连 HTTP 200、标题与正文可读。
- 已实现 `collectors/ggzy.py`（反爬组）：探测到风控即优雅降级返回 0 条并记录原因，靠调度器冷却 2 分钟后重试，不伪造数据。

### 采集分组调度（应对限流/反爬站点的优化）
- `collectors/scheduler.py` 把数据源分 open（免爬，连续抓）与 throttled（反爬，低频轮询）两组。
- throttled 组 round-robin：每个站点抓一次换下一个，同一站点两次任务间隔 ≥ `cooldown_sec`（默认 120 秒），全部冷却时睡到最近到期站点；失败也计入冷却，最多 `max_attempts` 次。
- 实测：免爬组连续抓 land_market 27 + mining 200 + ejy 836 条；ggzy 两次降级（间隔 2 分钟）均返回 0 条并记 `blocked`。假时钟单测验证轮询顺序与冷却间隔正确。

### 第二批：国资委认定产权交易机构（2026-11-25）
依据国资厅产权〔2020〕333 号文，36 家机构全部有公开平台并查到挂牌信息（完整清单见工作区 `output/sasac_property_exchanges.md`）。已接入 5 家，实测共 **201 条**全部入库，全量重算后库内 2381 条：

- **武汉光谷 `ovupre.com`**：`GET /index/new_getxxmm.html?pageSize=20&pageNo=N&index={2|1|3}`，JSON 字段 `XMMC/XMBH/ZRDJ/KSRQ/JSRQ/URL`；实测 65 条（含 BC 双推 6 条）。
- **深圳联合 `sotcbb.com`**：`POST /api/v1/sotcbb/local/project/list`，body 带 `targetColumnIds:["3226"]`，返回 `title/projectNo/listingPriceUnits/registerFrom/registerTo/targetRegion`；实测 60 条。
- **厦门产权 `xemas.com.cn`**：`POST /cms/article/query?size=&page=&getData=true&getResource=true`，body 带 `categorys:["a22482fe-…getProgeniture"]`（分类树），返回 `title/data.listingPrice/data.sellerName/userdefine3/userdefine5`；实测 60 条。注意 URL 参数形式拿不到数据，必须用分类树 POST。
- **青海产权 `qhcqjy.com`**：`GET /item.do?para=viewlist&classCode=3001&ass={01|02|03|07|16}`，**GBK 编码**；列表只给标题，详情抓 `para=viewcontent` 提取挂牌价/评估价/面积；实测 10 条。
- **贵州阳光 `prechina.net`**：`GET /project/` 静态列表，项目编号/挂牌时间/挂牌价在 span 中；实测 6 条。

**未接入（保持人工查看，不绕策略）**：
- 甘肃 `gscq.com.cn`：本机出口持续 HTTP 403（WAF），不尝试绕过。
- 大连 `daee.cn` / 河南 `zycqjy.com`：zbxsoft 系统接口 `/web/proList/home` 返回 `{"result":"F","message":"Source must not be null"}`，公开页面未暴露该参数来源，暂不接入。

**不重复接入**：内蒙古（`nmgcqjy.ejy365.com`）、新疆（`xjcqjy.ejy365.com`）、黑龙江等机构把项目挂在 e交易 子站，现有 `ejy` 采集器已覆盖；按 `source + external_id` 去重即可。

### 第三批：全国产权交易门户 + 省级平台可抓性（2026-11-25）

**全国产权行业信息化综合服务平台 `cspea.com.cn`（已接入，优先级最高）**

该站定位为全国产权交易资本市场统一门户，首页和项目中心公开展示全国各交易所挂牌标的，**无需登录、无验证码、无 JS 校验**：

- 列表 `GET /list?c={C01..C06}&s=A02,A03`：SSR 页面 `<script>` 内嵌 `window` 状态，其中 `listData.datas` 为项目数组，字段含 `projectCode / projectName / projectPrice`（万元）/ `zoneName / publishDate / expireDate / tradInstitutionName`（来源交易所）/ `projectClassifyCode`。实测分类总量：C01 资产转让 62240、C02 产权转让 1349、C03 企业增资 112、C04 金融资产 607、C05 不良资产 434、C06 债权 44。
- 列表每次只返回最新 12 条，且在两组缓存间轮换（已用连续 3 次请求验证）；配置 `repeat: 3` 后每类可拿约 20+ 条，6 类合计去重 65 条。
- 详情 `GET /list/{c01..c06}/{projectCode小写}`：静态页，内嵌 `projectDetailData`，含 `assess.objectEvaluateValue`（评估价）、`seller[].sellerName`、`swProject.importantInfo`（瑕疵/风险说明）、`project.projectUrl`（来源交易所原链接）。取最新 40 条抓详情，实测 33 条拿到评估价，可直接作为 v2 评分的"评估价优先"基准。
- 实测结果：40 条入库，分类 B 22 / BC 1 / C 17，均分 59.2（最高 77），全量重算后总库 2452 条，API 与 `/admin` 均可查。
- 公开接口 `/api/enjoyProject/getProjectList` 等需要额外鉴权参数（返回"参数不合法"），**不猜测内部参数**，走 SSR 公开页面。

**其余省级交易所可抓性（2026-11-25 低频实测，每站首页仅 1 次请求）**

14 家未接入省级站点全部 HTTP 200 可访问，但"能否直接抓到项目"差异明显：

| 站点 | 实测结论 | 建议 |
|---|---|---|
| 福建 `fjcqjy.com` | 首页 38 条 `/html/list-content-*.html` 项目详情链接，静态 HTML | 可接入，优先级高 |
| 江西 `jxcq.jxggzyjy.cn` | 有"正式挂牌项目"栏目 `project_center.html`，但列表靠 JS 加载，页面源码无项目条目 | 需先定位列表接口 |
| 青岛 `cqjy.qdcq.net` | 明确项目列表入口 `portal/pro/items.jsp` | 可接入，优先级中 |
| 天津 `tpre.cn` / 沈阳 `sprtc.com` | 有公告栏目 `news/jysgg.html`、`gghz1/xmgg.htm` | 可接入，优先级中 |
| 浙江 `zjpse.com` | 首页挂牌关键词多，但项目跳 `shipbid.net`，前端渲染 | 需定位接口；其项目已大量出现在 cspea |
| 广东联合 / 北部湾 / 海南 / 云南 / 西部 / 宁夏 / 宁波 | 首页有挂牌关键词但无直出项目链接，列表在子栏目/JS | 暂不接，cspea 已覆盖其挂牌项目 |
| 湖南 `hnaee.com` | 首页无可提取关键词与项目链接 | 暂不接 |

**结论**：cspea 一个源已覆盖全国交易所的最新挂牌，且带评估价，边际价值高于逐个铺开省级站点。后续要扩量，优先调大 cspea 的 `repeat` / `max_detail`，再按上表接入福建、青岛、天津、沈阳。北京、江苏、甘肃、大连、河南仍按合规边界维持人工查看。
