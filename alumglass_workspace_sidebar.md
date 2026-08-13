# AlumGlass Workspace Sidebar

> Tài liệu mô tả dễ đọc tương ứng với `alumglass_workspace_sidebar.json`.
> Tổng cộng: **11 Workspace**, **131 Sidebar Items**.
> Tổng cộng: **{} Workspace**, **{} Sidebar Items**.

## Quy ước

- `Section Break` → tiêu đề nhóm trên Workspace.
- `Link` + `child: 1` → mục DocType/Workspace nằm trong nhóm.
- `Home` → liên kết về Workspace hiện tại.
- Các Child Table không được đưa lên Sidebar.

---

## 1. Master Data

- **Workspace:** `Master Data`
- **Module:** `AL Master Data`
- **App:** `alumglass`

### Sidebar

- 🏠 **Home** → `Master Data`

### Core Masters

  - **Item** → DocType: `Item`
  - **Item Group** → DocType: `Item Group`
  - **Brand** → DocType: `Brand`
  - **UOM** → DocType: `UOM`

### Material

  - **AL Material Category** → DocType: `AL Material Category`
  - **AL Slug Library** → DocType: `AL Slug Library`
  - **AL Color Standard** → DocType: `AL Color Standard`

### Profile & Glass

  - **AL Profile System** → DocType: `AL Profile System`
  - **AL Glass Type** → DocType: `AL Glass Type`
  - **AL Glass Master** → DocType: `AL Glass Master`

### Product

  - **AL Product Type** → DocType: `AL Product Type`

### Pricing Dimensions

  - **AL Pricing Dimension** → DocType: `AL Pricing Dimension`
  - **AL Variable Dimension Mapping** → DocType: `AL Variable Dimension Mapping`

### Formula Variables

  - **AL Variable Set** → DocType: `AL Variable Set`
  - **AL Variable Library** → DocType: `AL Variable Library`

---

## 2. BOM & Pricing

- **Workspace:** `BOM & Pricing`
- **Module:** `AL BOM Engine`
- **App:** `alumglass`

### Sidebar

- 🏠 **Home** → `BOM & Pricing`

### BOM

  - **AL Bom Set** → DocType: `AL Bom Set`
  - **AL BOM** → DocType: `AL BOM`
  - **AL BOM Version** → DocType: `AL BOM Version`
  - **AL Design Revision** → DocType: `AL Design Revision`

### Costing

  - **AL Cost Bucket** → DocType: `AL Cost Bucket`
  - **AL Cost Template** → DocType: `AL Cost Template`

### Accessories

  - **AL Accessory Set** → DocType: `AL Accessory Set`

### Snapshots

  - **ConfigSnapshot** → DocType: `ConfigSnapshot`

---

## 3. Formula & Rules

- **Workspace:** `Formula & Rules`
- **Module:** `AL Formula & Rules`
- **App:** `alumglass`

### Sidebar

- 🏠 **Home** → `Formula & Rules`

### Calculation Rules

  - **AL Calculation Rule** → DocType: `AL Calculation Rule`

### Dynamic Item Rules

  - **AL Dynamic Item Rule** → DocType: `AL Dynamic Item Rule`
  - **AL Dynamic Item Rule Version** → DocType: `AL Dynamic Item Rule Version`

### Quantity Calculation

  - **AL Quantity Calc Method** → DocType: `AL Quantity Calc Method`

---

## 4. Selling

- **Workspace:** `Selling`
- **Module:** `AL Selling`
- **App:** `alumglass`

### Sidebar

- 🏠 **Home** → `Selling`

### CRM

  - **Lead** → DocType: `Lead`
  - **Opportunity** → DocType: `Opportunity`

### Sales

  - **Customer** → DocType: `Customer`
  - **Quotation** → DocType: `Quotation`
  - **Sales Order** → DocType: `Sales Order`

### Projects

  - **Project** → DocType: `Project`

---

## 5. Buying

- **Workspace:** `Buying`
- **Module:** `AL Buying`
- **App:** `alumglass`

### Sidebar

- 🏠 **Home** → `Buying`

### Suppliers

  - **Supplier** → DocType: `Supplier`
  - **AL Supplier Price List** → DocType: `AL Supplier Price List`

### Material Planning

  - **AL Material Plan** → DocType: `AL Material Plan`

### Purchasing

  - **Purchase Order** → DocType: `Purchase Order`
  - **Purchase Receipt** → DocType: `Purchase Receipt`
  - **Purchase Invoice** → DocType: `Purchase Invoice`

### Cost Control

  - **AL Cost Variance** → DocType: `AL Cost Variance`

---

## 6. Stock

- **Workspace:** `Stock`
- **Module:** `AL Stock`
- **App:** `alumglass`

### Sidebar

- 🏠 **Home** → `Stock`

### Inventory

  - **Item** → DocType: `Item`
  - **Warehouse** → DocType: `Warehouse`
  - **Batch** → DocType: `Batch`
  - **Serial No** → DocType: `Serial No`

### Project Stock

  - **AL Project Warehouse Map** → DocType: `AL Project Warehouse Map`

### Transactions

  - **Stock Entry** → DocType: `Stock Entry`
  - **Delivery Note** → DocType: `Delivery Note`

---

## 7. Manufacturing

- **Workspace:** `Manufacturing`
- **Module:** `AL Manufacturing`
- **App:** `alumglass`

### Sidebar

- 🏠 **Home** → `Manufacturing`

### Cutting Standards

  - **AL Cutting Standard** → DocType: `AL Cutting Standard`

### Aluminum Cutting

  - **AL Cutting Plan (Aluminum)** → DocType: `AL Cutting Plan (Aluminum)`

### Glass Cutting

  - **AL Cutting Plan (Glass)** → DocType: `AL Cutting Plan (Glass)`

### Production

  - **AL Production Order Bridge** → DocType: `AL Production Order Bridge`
  - **Work Order** → DocType: `Work Order`

### Quality

  - **Quality Inspection** → DocType: `Quality Inspection`

---

## 8. Construction

- **Workspace:** `Construction`
- **Module:** `AL Construction`
- **App:** `alumglass`

### Sidebar

- 🏠 **Home** → `Construction`

### Project

  - **Project** → DocType: `Project`
  - **Task** → DocType: `Task`
  - **Timesheet** → DocType: `Timesheet`

### Site Survey

  - **AL Site Survey** → DocType: `AL Site Survey`

### Installation

  - **AL Installation Team** → DocType: `AL Installation Team`
  - **AL Installation Order** → DocType: `AL Installation Order`
  - **AL Installation Progress** → DocType: `AL Installation Progress`
  - **AL Installation Cost Actual** → DocType: `AL Installation Cost Actual`

### Changes

  - **AL Change Order** → DocType: `AL Change Order`

### Handover

  - **AL Handover Acceptance** → DocType: `AL Handover Acceptance`

---

## 9. Project Accounting

- **Workspace:** `Project Accounting`
- **Module:** `AL Account`
- **App:** `alumglass`

### Sidebar

- 🏠 **Home** → `Project Accounting`

### Project Finance

  - **AL Project Profitability Snapshot** → DocType: `AL Project Profitability Snapshot`
  - **AL Project Financial Config** → DocType: `AL Project Financial Config`

### Budget & Cost

  - **Budget** → DocType: `Budget`
  - **Cost Center** → DocType: `Cost Center`
  - **Accounting Dimension** → DocType: `Accounting Dimension`

### Payments

  - **Payment Schedule** → DocType: `Payment Schedule`
  - **Journal Entry** → DocType: `Journal Entry`
  - **Payment Entry** → DocType: `Payment Entry`

---

## 10. Quality & Warranty

- **Workspace:** `Quality & Warranty`
- **Module:** `AL Quality`
- **App:** `alumglass`

### Sidebar

- 🏠 **Home** → `Quality & Warranty`

### Quality

  - **Quality Inspection** → DocType: `Quality Inspection`

### Warranty

  - **AL Warranty Policy** → DocType: `AL Warranty Policy`
  - **Warranty Claim** → DocType: `Warranty Claim`

### Maintenance

  - **Maintenance Visit** → DocType: `Maintenance Visit`
  - **Maintenance Schedule** → DocType: `Maintenance Schedule`

---

## 11. AI & Intelligence

- **Workspace:** `AI & Intelligence`
- **Module:** `AL AI`
- **App:** `alumglass`

### Sidebar

- 🏠 **Home** → `AI & Intelligence`

### AI

  - **AL AI Suggestion Log** → DocType: `AL AI Suggestion Log`
  - **AL AI Interaction Log** → DocType: `AL AI Interaction Log`

### Alerts

  - **AL Alert Config** → DocType: `AL Alert Config`

---

# Tổng quan Navigation

```text
AlumGlass
│
├── Master Data
├── BOM & Pricing
├── Formula & Rules
├── Selling
├── Buying
├── Stock
├── Manufacturing
├── Construction
├── Project Accounting
├── Quality & Warranty
└── AI & Intelligence
```
