# 蘋果 UI/UX 開發指引

> 適用對象：產品經理、UI/UX 設計師、iOS/macOS/iPadOS/watchOS/visionOS 開發者  
> 目的：建立一套簡單、清楚、可落地的 Apple 風格 UI/UX 開發準則  
> 主要依據：Apple Human Interface Guidelines、Apple Developer Documentation、Apple Design Resources、WWDC 設計與開發影片

---

## 0. 一句話原則

Apple UI/UX 的核心不是「白底、圓角、模糊玻璃」，而是：

**內容優先、系統原生、互動克制、層級清楚、可存取性完整、跨平台但不硬搬。**

做 Apple 平台產品時，最好的設計通常不是讓使用者注意到 UI，而是讓使用者自然完成任務。

---

## 1. 核心設計原則

### 1.1 內容優先

介面應該支撐內容，而不是搶走內容的注意力。

實務準則：

- 首屏先呈現使用者最關心的內容或任務。
- 不要為了品牌識別而過度裝飾每個區塊。
- 避免在主畫面放太多次要功能、促銷、橫幅或干擾元素。
- 導覽、按鈕、工具列應服務內容流，而不是成為視覺主角。

錯誤傾向：

```text
先做一個很炫的 header，再把功能塞進去。
```

正確傾向：

```text
先定義使用者要完成的任務，再決定需要哪些 UI 元件。
```

---

### 1.2 系統原生優先

Apple 平台使用者已經熟悉系統互動模式。除非有強理由，否則應優先使用系統元件。

優先使用：

- SwiftUI：`NavigationStack`、`TabView`、`List`、`Form`、`Sheet`、`Toolbar`、`Button`、`Menu`
- UIKit：`UINavigationController`、`UITabBarController`、`UITableView`、`UICollectionView`、`UISheetPresentationController`
- AppKit：`NSWindow`、`NSToolbar`、`NSSplitViewController`、`NSCollectionView`

避免：

- 自製 navigation bar
- 自製 tab bar
- 自製 alert
- 自製 picker
- 自製 scroll behavior
- 自製返回手勢

除非產品有非常強的互動需求，否則自製基礎元件通常會帶來 accessibility、深色模式、鍵盤操作、動畫一致性與維護成本問題。

---

### 1.3 熟悉感比獨特感重要

Apple 風格重視「看起來像這個平台上的 app」。

設計時要問：

- 使用者是否能不用教學就知道怎麼操作？
- 這個互動是否符合 iOS/macOS/watchOS/visionOS 的慣例？
- 這個畫面是否能自然支援深色模式、Dynamic Type、VoiceOver？
- 我們是否只是為了品牌感而破壞平台一致性？

---

### 1.4 克制而明確

Apple UI 通常不依賴大量線框、陰影、色塊來建立層次，而是使用：

- 留白
- 字級
- 語意色彩
- 系統材質
- 動態回饋
- 內容群組
- 標準元件狀態

介面越簡單，越需要層級設計精準。

---

## 2. 平台策略

### 2.1 不要把 iPhone 畫面直接放大成 iPad/Mac

Apple 平台雖然可以共用設計語言，但不同裝置的使用情境不同。

| 平台 | 設計重點 | 常見結構 |
|---|---|---|
| iPhone | 單手操作、垂直流程、清楚導覽 | Tab bar、Navigation stack、Sheet |
| iPad | 多欄、分割視圖、多工 | Sidebar、Split view、Floating panels |
| macOS | 視窗、多任務、鍵盤滑鼠、選單列 | Sidebar、Toolbar、Inspector、Menu bar |
| watchOS | 快速 glance、短互動、即時資訊 | List、Complication、Smart Stack |
| visionOS | 空間、深度、注視與手勢 | Window、Volume、Immersive Space |

### 2.2 跨平台設計原則

可以共用：

- 品牌語氣
- 資訊架構
- 主要任務流程
- 圖示語意
- 內容模型
- 設計 token

不應硬共用：

- 版面比例
- 導覽方式
- hover/focus 狀態
- 工具列密度
- 視窗與分欄策略
- 操作手勢

---

## 3. 資訊架構與導覽

### 3.1 先決定 app 的主要結構

常見結構：

1. **Tab-based app**  
   適合 3–5 個主要區域，例如首頁、搜尋、收藏、設定。

2. **Navigation stack app**  
   適合從列表進入詳情，例如文章、商品、任務、訊息。

3. **Sidebar app**  
   適合 iPad/macOS，支援多分類、多文件、多工作區。

4. **Document-based app**  
   適合使用者建立、管理、編輯文件或專案。

5. **Utility app**  
   適合功能單純、任務明確的工具型產品。

---

### 3.2 Tab bar 使用準則

適合使用 tab bar 的情況：

- app 有幾個同等重要的主要區域。
- 使用者會頻繁切換區域。
- 每個 tab 代表穩定、長期存在的目的地。

避免：

- 超過 5 個主要 tab。
- 把一次性功能放進 tab。
- tab 文字太長。
- tab icon 語意不清。
- 用 tab 表示流程步驟。

命名原則：

```text
好：首頁、搜尋、收藏、帳戶
差：探索最新內容、我的所有收藏、個人資料與設定
```

---

### 3.3 Navigation stack 使用準則

適合：

- 列表 → 詳情
- 分類 → 子分類 → 內容
- 設定 → 設定項目
- 文件清單 → 文件編輯

注意：

- 每一層都要有清楚標題。
- 返回行為要符合系統預期。
- 不要讓使用者進入過深層級。
- 重要操作不要只藏在最深層頁面。

---

### 3.4 Sheet 使用準則

Sheet 適合短流程或補充任務，例如：

- 新增項目
- 編輯欄位
- 選擇篩選條件
- 登入
- 分享
- 快速設定

避免：

- 在 sheet 裡再疊太多 sheet。
- 把完整主流程塞進 sheet。
- 使用者無法理解關閉後會發生什麼。
- 表單未儲存時直接關閉而無提示。

---

## 4. 版面與間距

### 4.1 留白是層級工具

留白不是浪費空間，而是幫助使用者理解資訊分組。

實務準則：

- 相關內容靠近。
- 不相關內容拉開。
- 頁面邊界使用平台常見 margin。
- 避免把所有內容平均塞滿。
- 空間不足時優先調整資訊層級，不是直接縮小文字。

---

### 4.2 對齊比裝飾重要

Apple UI 常見明確的垂直與水平對齊。

檢查方式：

- 標題、內文、按鈕是否有一致起點？
- 列表內 icon、文字、輔助文字是否對齊？
- 卡片、欄位、分隔線是否形成清楚節奏？
- 多欄畫面是否有一致 grid？

---

### 4.3 不要濫用卡片

卡片適合表達獨立物件或模組，但不是所有內容都需要卡片。

適合卡片：

- 商品
- 文章
- 任務
- 統計摘要
- 獨立功能入口

不適合卡片：

- 每一個設定項
- 每一段普通文字
- 每一個表單欄位
- 已經在 list/form 裡的內容

---

## 5. 視覺風格

### 5.1 字體

Apple 平台預設使用 San Francisco 系列字體。開發時應優先使用語意字級，而不是硬編固定 px/pt。

SwiftUI 建議：

```swift
Text("帳戶")
    .font(.title2)

Text("付款方式")
    .font(.headline)

Text("你的付款資訊會安全儲存。")
    .font(.subheadline)
    .foregroundStyle(.secondary)
```

避免：

```swift
Text("帳戶")
    .font(.system(size: 23))
    .foregroundColor(.black)
```

原因：

- 語意字級可支援 Dynamic Type。
- 系統色彩可支援深色模式與高對比。
- 未來系統調整字體度量時，app 較能自然跟上。

---

### 5.2 色彩

Apple UI 不鼓勵大量硬編色彩。應優先使用語意色彩。

建議：

```swift
Text("主要文字")
    .foregroundStyle(.primary)

Text("輔助文字")
    .foregroundStyle(.secondary)

Button("完成") {
    save()
}
.tint(.accentColor)
```

避免：

```swift
.foregroundColor(Color(red: 0, green: 0, blue: 0))
.background(Color.white)
```

色彩準則：

- 品牌色用於強調，不應覆蓋整個介面。
- 危險操作使用 destructive 語意。
- 成功、警告、錯誤狀態要同時搭配文字或圖示，不要只靠顏色。
- 深色模式必測。
- 高對比模式必測。

---

### 5.3 圖示

優先使用 SF Symbols。

使用準則：

- 圖示語意要清楚。
- 同一組圖示使用一致 weight 與 scale。
- 圖示旁有文字時，不要讓圖示搶過文字。
- 導覽用圖示應避免太抽象。
- 重要操作不要只靠圖示表示。

範例：

```swift
Label("新增", systemImage: "plus")
Label("刪除", systemImage: "trash")
Label("分享", systemImage: "square.and.arrow.up")
```

---

### 5.4 Liquid Glass 與材質

在 iOS 26+、macOS 26+ 與新一代 Apple 設計語言中，Liquid Glass 是重要的視覺材料。它應主要用於控制項與導覽層，讓它們和內容層形成區隔。

使用準則：

- 適合用於 tab bar、toolbar、sidebar、控制項背景、浮動操作區。
- 不要把主要內容本身做成大量玻璃效果。
- 玻璃效果不能犧牲文字可讀性。
- 透明、模糊、折射效果應服務層級，不是純裝飾。
- 自訂 glass UI 前，先確認系統元件是否已經提供相同效果。

檢查問題：

```text
這個 glass 元素是否真的代表控制層？
底下內容是否會干擾文字可讀性？
使用者是否能立刻分辨內容與控制項？
深色模式下是否仍然清楚？
高對比或降低透明度設定下是否可用？
```

---

## 6. 元件設計準則

### 6.1 Button

按鈕要清楚表達動作。

好例子：

```text
儲存
加入購物車
建立活動
刪除帳號
```

差例子：

```text
好
確認
送出
下一步
```

使用準則：

- 一個區域只保留一個主要動作。
- 危險動作用 destructive 樣式。
- loading 時要避免重複點擊。
- disabled 狀態要讓使用者知道原因。
- 按鈕文字使用動詞或動詞片語。

SwiftUI 範例：

```swift
Button("儲存") {
    save()
}
.buttonStyle(.borderedProminent)

Button("刪除", role: .destructive) {
    delete()
}
```

---

### 6.2 List

List 是 Apple UI 的核心元件之一。

使用準則：

- 每列只放必要資訊。
- 主文字、輔助文字、狀態文字要有明確層級。
- 可點擊列應有一致互動回饋。
- 列表排序要符合使用者預期。
- 空狀態要清楚說明下一步。

SwiftUI 範例：

```swift
List(items) { item in
    NavigationLink {
        DetailView(item: item)
    } label: {
        VStack(alignment: .leading) {
            Text(item.title)
                .font(.headline)
            Text(item.subtitle)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }
}
.navigationTitle("項目")
```

---

### 6.3 Form

表單要降低輸入負擔。

準則：

- 只問必要資訊。
- 欄位順序符合使用者心智模型。
- 錯誤訊息靠近欄位。
- 即時驗證要避免過度打擾。
- 輸入格式要自動輔助，例如數字鍵盤、日期選擇器。
- 儲存成功要有明確回饋。

---

### 6.4 Alert 與 Confirmation Dialog

Alert 應用於需要立即注意的情況，不應拿來做普通提示。

適合：

- 危險操作確認
- 權限或資料遺失提醒
- 重大錯誤

不適合：

- 每次儲存成功都跳 alert
- 一般說明文字
- 可以在畫面中直接呈現的錯誤

按鈕順序與文案要明確：

```text
取消 / 刪除
保留草稿 / 放棄變更
稍後 / 開啟設定
```

---

### 6.5 Toolbar

Toolbar 應放高頻、與目前內容相關的操作。

準則：

- 不要塞滿工具列。
- 常用操作放外面，低頻操作放 menu。
- icon-only 按鈕要有 accessibility label。
- toolbar item 群組要符合功能關係。
- iOS、iPadOS、macOS 的 toolbar 密度應分別設計。

---

## 7. 互動與動效

### 7.1 動畫要有原因

Apple 風格的動畫通常用來說明狀態改變或空間關係。

適合動畫：

- 畫面進入與離開
- sheet 展開
- 清單新增或刪除
- 狀態切換
- 拖曳排序
- loading 進度

避免：

- 無意義 bounce
- 每個元素都做入場動畫
- 動畫時間過長
- 和手勢方向不一致
- 造成暈動或可讀性下降

---

### 7.2 直接操作感

使用者應感覺正在直接操作物件，而不是操作抽象系統。

做法：

- 拖曳時物件跟隨手指或游標。
- 點擊後有即時視覺回饋。
- 操作結果出現在操作位置附近。
- 轉場方向符合空間邏輯。
- 可取消或可復原的操作要提供清楚出口。

---

### 7.3 Loading、進度與延遲

準則：

- 短延遲不一定要顯示 spinner。
- 長任務要顯示進度或狀態。
- 可背景執行的任務不應阻塞整個 app。
- 避免 skeleton 與 spinner 同時過度使用。
- 失敗時提供下一步，而不只是說「發生錯誤」。

---

## 8. 可存取性 Accessibility

Accessibility 不是最後補上的功能，而是 UI/UX 的基本品質。

### 8.1 基本要求

每個可互動元素都應該：

- 有清楚的 accessibility label。
- 有正確的 role/trait。
- 狀態可被 VoiceOver 理解。
- 點擊區域足夠大。
- 支援 Dynamic Type。
- 支援深色模式。
- 支援高對比。
- 支援降低動態效果。
- 不只靠顏色傳達資訊。

---

### 8.2 SwiftUI 範例

```swift
Button {
    favorite.toggle()
} label: {
    Image(systemName: favorite ? "heart.fill" : "heart")
}
.accessibilityLabel(favorite ? "取消收藏" : "加入收藏")
.accessibilityHint("切換此項目的收藏狀態")
```

---

### 8.3 Dynamic Type

避免固定高度卡死文字。

不建議：

```swift
Text(description)
    .frame(height: 40)
```

建議：

```swift
Text(description)
    .font(.body)
    .fixedSize(horizontal: false, vertical: true)
```

---

### 8.4 可存取性測試清單

- VoiceOver 能否完成主要流程？
- 所有 icon-only button 是否有 label？
- 字級調到最大時版面是否仍可用？
- 深色模式是否有足夠對比？
- 降低透明度後介面是否仍清楚？
- 降低動態效果後是否仍能理解狀態變化？
- 錯誤訊息是否能被螢幕閱讀器讀到？
- 表單欄位是否有明確標籤？

---

## 9. 文案 UX Writing

### 9.1 文案要短、清楚、有行動性

Apple 風格文案通常直接、自然、避免技術術語。

好：

```text
無法連線。請檢查網路後再試一次。
```

差：

```text
Error code -1009. Request failed due to connectivity exception.
```

---

### 9.2 Button 文案

按鈕應說明按下後會發生什麼。

好：

```text
儲存變更
建立帳戶
加入收藏
刪除照片
```

差：

```text
確定
送出
OK
是
```

---

### 9.3 空狀態

空狀態要回答三件事：

1. 目前為什麼沒有內容？
2. 使用者可以做什麼？
3. 是否需要一個主要操作？

範例：

```text
還沒有收藏項目
看到喜歡的內容時，點一下愛心就會出現在這裡。
[開始瀏覽]
```

---

### 9.4 錯誤狀態

錯誤訊息要包含：

- 發生了什麼
- 為什麼可能發生
- 使用者可以怎麼處理

範例：

```text
無法儲存變更
你的網路連線似乎不穩定。請確認連線後再試一次。
[再試一次]
```

---

## 10. 權限、隱私與信任

Apple 使用者對權限、隱私與資料使用非常敏感。任何權限要求都應該有清楚理由。

準則：

- 不要在 app 啟動時一次要求所有權限。
- 在需要功能時才要求權限。
- 系統權限彈窗出現前，先用畫面說明價值。
- 說明要具體，不要模糊。
- 被拒絕後提供替代流程或設定入口。

好：

```text
允許相機權限後，你可以直接掃描收據，不需要手動輸入。
```

差：

```text
我們需要相機權限以提供更好的體驗。
```

---

## 11. 開發落地準則

### 11.1 SwiftUI 優先使用語意 API

建議：

```swift
struct SettingsView: View {
    var body: some View {
        NavigationStack {
            Form {
                Section("帳戶") {
                    NavigationLink("個人資料") {
                        ProfileView()
                    }
                    NavigationLink("付款方式") {
                        PaymentView()
                    }
                }

                Section("偏好設定") {
                    Toggle("通知", isOn: .constant(true))
                    Toggle("深色模式", isOn: .constant(false))
                }
            }
            .navigationTitle("設定")
        }
    }
}
```

這種寫法會自動獲得許多平台行為，例如 navigation、form spacing、Dynamic Type、深色模式與 accessibility 支援。

---

### 11.2 避免硬編視覺值

不建議：

```swift
Text("Hello")
    .font(.system(size: 16))
    .foregroundColor(.black)
    .padding(13)
```

較建議：

```swift
Text("Hello")
    .font(.body)
    .foregroundStyle(.primary)
    .padding()
```

必要時可以建立 design token，但 token 也應尊重平台語意。

---

### 11.3 狀態驅動 UI

UI 應該由狀態決定，而不是散落在多處手動改畫面。

常見狀態：

```swift
enum ViewState {
    case idle
    case loading
    case loaded([Item])
    case empty
    case failed(Error)
}
```

畫面根據狀態呈現：

```swift
switch state {
case .loading:
    ProgressView()
case .loaded(let items):
    ItemList(items: items)
case .empty:
    ContentUnavailableView("沒有項目", systemImage: "tray")
case .failed:
    ErrorView()
default:
    EmptyView()
}
```

---

### 11.4 Preview 驅動開發

每個重要畫面至少建立以下 preview：

- 一般資料
- 空狀態
- loading
- error
- 深色模式
- 大字級
- 小螢幕
- iPad 寬版

範例：

```swift
#Preview("Dark / Large Text") {
    SettingsView()
        .preferredColorScheme(.dark)
        .environment(\.dynamicTypeSize, .accessibility3)
}
```

---

### 11.5 設計系統最小集合

Apple-like app 不一定需要龐大 design system，但至少要定義：

- Typography usage
- Color semantics
- Spacing scale
- Icon usage
- Button hierarchy
- List row pattern
- Empty/error/loading states
- Form behavior
- Motion rules
- Accessibility rules

---

## 12. 常見 Apple-like UI 模式

### 12.1 設定頁

建議使用 `Form` 或平台原生 grouped list。

結構：

```text
設定

帳戶
- 個人資料
- 付款方式

通知
- 推播通知
- Email 通知

關於
- 版本
- 隱私權政策
```

---

### 12.2 詳情頁

結構：

```text
Title
Subtitle / metadata
Main content
Primary action
Secondary information
Related actions
```

準則：

- 最重要資訊放最上方。
- 行動按鈕靠近決策位置。
- 次要操作放 toolbar 或 menu。
- 危險操作不要和主要操作混在一起。

---

### 12.3 搜尋

搜尋體驗應該支援：

- 最近搜尋
- 建議關鍵字
- 即時結果或明確提交
- 無結果狀態
- 清除搜尋
- 篩選條件

準則：

- 搜尋欄位置要符合平台慣例。
- 不要讓篩選器壓過結果。
- 無結果時提供修正建議。

---

### 12.4 Onboarding

Onboarding 應短且有價值。

準則：

- 不要用 5 頁以上介紹所有功能。
- 優先讓使用者完成第一個有效行為。
- 權限要求要在情境中出現。
- 可以跳過。
- 不要把行銷文案偽裝成必要教學。

---

## 13. 設計交付規格

設計師交付給工程時，至少包含：

- 畫面目的
- 使用者任務
- 導覽來源與去向
- 元件狀態
- 空狀態
- 錯誤狀態
- loading 狀態
- 深色模式
- 大字級狀態
- 權限拒絕狀態
- 動畫或轉場說明
- accessibility label 建議
- 使用哪個系統元件

不夠好的交付：

```text
只給一張靜態 Figma 畫面。
```

好的交付：

```text
畫面 + 狀態 + 行為 + 元件語意 + 邊界情境。
```

---

## 14. 工程驗收清單

### 14.1 UI 一致性

- [ ] 使用系統元件優先。
- [ ] navigation 行為符合平台慣例。
- [ ] tab/sidebar/toolbar 結構清楚。
- [ ] 主要操作與次要操作層級明確。
- [ ] 版面在小螢幕與大螢幕都可用。
- [ ] 深色模式正常。
- [ ] 橫向與直向畫面正常。

### 14.2 UX 狀態

- [ ] loading 狀態完整。
- [ ] 空狀態完整。
- [ ] error 狀態完整。
- [ ] 權限拒絕狀態完整。
- [ ] 離線狀態完整。
- [ ] 表單驗證清楚。
- [ ] 危險操作有確認或可復原機制。

### 14.3 Accessibility

- [ ] VoiceOver 可完成主要流程。
- [ ] icon-only controls 有 accessibility label。
- [ ] Dynamic Type 最大字級仍可用。
- [ ] 不只靠顏色傳達狀態。
- [ ] 觸控目標足夠大。
- [ ] 降低動態效果後仍可理解。
- [ ] 降低透明度後仍可讀。

### 14.4 效能

- [ ] 列表滑動順暢。
- [ ] 圖片有快取與漸進載入策略。
- [ ] glass/material 效果未過度濫用。
- [ ] 動畫不造成卡頓。
- [ ] 首次載入時間可接受。
- [ ] 不必要的重繪已避免。

---

## 15. 常見錯誤與修正

### 錯誤 1：過度自訂 UI

問題：

```text
所有按鈕、列表、tab bar 都自己刻。
```

修正：

```text
先使用系統元件，只有品牌必要處做小幅調整。
```

---

### 錯誤 2：只做亮色模式

問題：

```text
文字與背景硬編 black/white。
```

修正：

```text
使用 .primary、.secondary、.background、.accentColor 等語意色彩。
```

---

### 錯誤 3：把裝飾當成層級

問題：

```text
每個區塊都加陰影、外框、漸層。
```

修正：

```text
先用文字、間距、分組與系統材質建立層級。
```

---

### 錯誤 4：錯誤訊息不可行動

問題：

```text
發生錯誤。
```

修正：

```text
無法儲存。請檢查網路後再試一次。
```

---

### 錯誤 5：忽略 accessibility

問題：

```text
等上架前再補 VoiceOver。
```

修正：

```text
設計與開發階段同步定義 label、狀態、字級與對比。
```

---

## 16. Apple UI/UX 的「十條鐵則」

1. 先讓任務清楚，再讓畫面漂亮。
2. 能用系統元件，就不要自己刻。
3. 導覽要符合平台慣例。
4. 文字、色彩、圖示使用語意 API。
5. 主要操作只能有一個視覺焦點。
6. 動畫要解釋狀態，不要表演。
7. 每個畫面都要有 loading、empty、error 狀態。
8. Accessibility 是基本規格，不是加分項。
9. iPhone、iPad、Mac 要分別設計，不要硬放大。
10. Apple-like 的最高標準是：使用者覺得自然，不需要學。

---

## 17. 建議團隊工作流程

### Step 1：定義任務

```text
使用者要完成什麼？
這件事多久做一次？
是在什麼裝置與情境下做？
```

### Step 2：選擇平台結構

```text
Tab、NavigationStack、Sidebar、Document、Utility？
```

### Step 3：套用系統元件

```text
先用 Apple 原生元件建立主要流程。
```

### Step 4：補齊狀態

```text
loading、empty、error、permission、offline、success。
```

### Step 5：做 accessibility 測試

```text
VoiceOver、Dynamic Type、Dark Mode、High Contrast、Reduce Motion。
```

### Step 6：做平台適配

```text
iPhone、iPad、Mac、watchOS、visionOS 分別檢查。
```

### Step 7：品牌化

```text
最後才加入品牌色、插圖、視覺語氣；不要先用品牌壓過平台。
```

---

## 18. 推薦官方參考資料

- Apple Human Interface Guidelines  
  https://developer.apple.com/design/human-interface-guidelines

- Designing for iOS  
  https://developer.apple.com/design/human-interface-guidelines/designing-for-ios

- Accessibility - Human Interface Guidelines  
  https://developer.apple.com/design/human-interface-guidelines/accessibility

- Layout - Human Interface Guidelines  
  https://developer.apple.com/design/human-interface-guidelines/layout

- Materials - Human Interface Guidelines  
  https://developer.apple.com/design/human-interface-guidelines/materials

- Color - Human Interface Guidelines  
  https://developer.apple.com/design/human-interface-guidelines/color

- Buttons - Human Interface Guidelines  
  https://developer.apple.com/design/human-interface-guidelines/buttons

- Tab bars - Human Interface Guidelines  
  https://developer.apple.com/design/human-interface-guidelines/tab-bars

- Toolbars - Human Interface Guidelines  
  https://developer.apple.com/design/human-interface-guidelines/toolbars

- Motion - Human Interface Guidelines  
  https://developer.apple.com/design/human-interface-guidelines/motion

- SwiftUI Documentation  
  https://developer.apple.com/documentation/swiftui

- SwiftUI Overview  
  https://developer.apple.com/swiftui/

- Apple Design Resources  
  https://developer.apple.com/design/resources/

- Meet Liquid Glass - WWDC25  
  https://developer.apple.com/videos/play/wwdc2025/219/

- Build a SwiftUI app with the new design - WWDC25  
  https://developer.apple.com/videos/play/wwdc2025/323/

---

## 19. 最終定義：什麼叫 Apple-like？

Apple-like 不等於：

```text
白色背景 + 大圓角 + 毛玻璃 + SF Symbols
```

Apple-like 應該是：

```text
使用者不用思考就知道下一步；
系統行為符合預期；
內容比裝飾重要；
互動有回饋且不干擾；
每個人都能使用；
在每個 Apple 裝置上都像原生體驗。
```

最終判斷標準：

**如果拿掉品牌 logo，使用者仍覺得這是一個自然、可靠、符合 Apple 平台習慣的 app，這才是好的 Apple UI/UX。**
