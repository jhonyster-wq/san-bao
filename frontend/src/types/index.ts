export interface Company {
  id: string;
  rut: string;
  legal_name: string;
  trade_name?: string;
  tax_activity?: string;
  address?: string;
  email?: string;
  phone?: string;
}

export interface User {
  id: string;
  username: string;
  email: string;
  is_superuser: boolean;
  first_name?: string;
  last_name?: string;
  roles?: string[];
  permissions?: string[];
}

export interface FinancialSummary {
  total_revenue: number;
  tuition_revenue: number;
  clinical_revenue: number;
  ecommerce_revenue: number;
  pending_receivables: number;
  hr_payroll_expenses: number;
  hr_fee_expenses: number;
  total_expenses: number;
  net_operating_result: number;
}

export interface AcademicKpis {
  total_active_students: number;
  active_cohorts: number;
  total_programs: number;
  accredited_clinical_hours: number;
}

export interface ClinicalKpis {
  total_patients: number;
  total_appointments: number;
  completed_appointments: number;
  active_practitioners: number;
  signed_clinical_encounters: number;
}

export interface ExecutiveDashboard {
  company_id?: string;
  company_name: string;
  financial: FinancialSummary;
  academic: AcademicKpis;
  clinical: ClinicalKpis;
}

export interface Patient {
  id: string;
  record_number: string;
  first_name: string;
  last_name: string;
  rut: string;
  gender: string;
  birth_date?: string;
  phone?: string;
  blood_type?: string;
}

export interface TCMDiagnosis {
  tongue_body_color?: string;
  tongue_shape?: string;
  tongue_coating_color?: string;
  tongue_coating_thickness?: string;
  pulse_rate?: string;
  left_wrist?: { cun?: string; guan?: string; chi?: string };
  right_wrist?: { cun?: string; guan?: string; chi?: string };
  syndrome_differentiation: string[];
  treatment_principle: string;
  acupuncture_points: string[];
}

export interface ClinicalEncounter {
  id: string;
  appointment_id: string;
  encounter_date: string;
  reason_for_consultation: string;
  anamnesis: string;
  tcm_diagnosis: TCMDiagnosis;
  status: 'DRAFT' | 'SIGNED' | 'AMENDED';
  hours_credited: number;
  tutor_signature?: string;
}

export interface HREmployee {
  id: string;
  employee_number: string;
  job_title: string;
  department: string;
  employee_type: 'TEACHER' | 'PRACTITIONER' | 'ADMINISTRATIVE' | 'EXECUTIVE';
  hire_date: string;
  status: string;
}

export interface HRPayroll {
  id: string;
  employee_id: string;
  period_month: number;
  period_year: number;
  worked_days: number;
  base_salary: number;
  legal_gratuity: number;
  gross_taxable_salary: number;
  total_earnings: number;
  total_deductions: number;
  net_salary: number;
  status: string;
}

export interface DTEDocument {
  id: string;
  dte_type: number;
  folio: number;
  issue_date: string;
  issuer_name: string;
  receiver_rut: string;
  receiver_name: string;
  total_amount: number;
  sii_status: string;
  digital_stamp?: string;
}
