export type Role = "officer" | "manager" | "admin";

export interface UserProfile {
  uid: string;
  name: string;
  email: string;
  role: Role;
  department?: string;
  is_active?: boolean;
  created_at?: string | null;
}

export type CustomerStatus = "active" | "archived";

export interface Customer {
  id: string;
  full_name: string;
  national_id?: string;
  phone?: string;
  address?: string;
  account_no?: string;
  status: CustomerStatus;
  created_by: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export type ProcessingStatus =
  | "pending"
  | "processing"
  | "validated"
  | "validation_failed"
  | "completed"
  | "error";

export interface Table1Row {
  month: string;
  debit: number;
  credit: number;
  diff: number;
  endBalance: number;
}

export interface Table2Row {
  month: string;
  debit: number;
  credit: number;
  diff: number;
}

export interface Table3Row {
  month: string;
  txnNumber: string;
  debit: number;
  description: string;
}

export interface Table3Group {
  amount: number;
  monthCount: number;
  rows: Table3Row[];
}

export interface ValidationInfo {
  matched: boolean;
  mismatchCount: number;
  checkedAt?: string | null;
}

export interface Statement {
  id: string;
  customer_id: string;
  file_name: string;
  storage_path: string;
  period_start?: string;
  period_end?: string;
  opening_balance?: number;
  total_transactions?: number;
  total_debit?: number;
  total_credit?: number;
  uploaded_by: string;
  uploaded_at?: string | null;
  processing_status: ProcessingStatus;
  validation?: ValidationInfo | null;
  table1Summary: Table1Row[];
  table2Summary: Table2Row[];
  table3Summary: Table3Group[];
  report_storage_path?: string;
  report_generated_at?: string | null;
  error_detail?: string;
}

export interface Transaction {
  date: string;
  txnNumber: string;
  description: string;
  debit: number;
  credit: number;
  balance: number;
}

export type ApprovalDecision = "approved" | "rejected" | "partial";

export interface Approval {
  id: string;
  decided_by: string;
  decided_at?: string | null;
  decision: ApprovalDecision;
  approved_amount: number;
  reason: string;
}

export type AuditAction =
  | "login"
  | "upload"
  | "process"
  | "approve"
  | "reject"
  | "view"
  | "download";

export interface AuditLog {
  id: string;
  user_id: string;
  user_email: string;
  action: AuditAction;
  target_type: "statement" | "customer" | "user";
  target_id: string;
  timestamp?: string | null;
  details: Record<string, unknown>;
}
