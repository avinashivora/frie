import svgPaths from "./svg-qcu94pqgtn";

function FormHeader() {
  return (
    <div className="[word-break:break-word] content-stretch flex flex-col gap-[12px] items-start leading-[normal] relative shrink-0 w-full" data-name="form-header">
      <p className="font-['Outfit:ExtraBold',sans-serif] font-extrabold relative shrink-0 text-[#0f172a] text-[32px] w-full">Welcome Back</p>
      <p className="font-['Geist:Regular',sans-serif] font-normal relative shrink-0 text-[#334155] text-[14px] w-full">Sign in to your financial diagnostic portal</p>
    </div>
  );
}

function Mail() {
  return (
    <div className="relative shrink-0 size-[16px]" data-name="mail">
      <svg className="absolute block inset-0 size-full" fill="none" height="16" preserveAspectRatio="none" viewBox="0 0 16 16" width="16">
        <g id="mail">
          <path d={svgPaths.p10d0c00} id="Vector" stroke="#94A3B8" strokeLinecap="round" strokeWidth="2" />
        </g>
      </svg>
    </div>
  );
}

function InputBox() {
  return (
    <div className="bg-[#f8fafc] content-stretch flex gap-[10px] items-center p-[12px] relative rounded-[8px] shrink-0 w-full" data-name="input-box">
      <div aria-hidden className="absolute border border-[#f1f5f9] border-solid inset-0 pointer-events-none rounded-[8px]" />
      <Mail />
      <p className="[word-break:break-word] flex-[1_0_0] font-['Geist:Regular',sans-serif] font-normal leading-[normal] min-w-px relative text-[#334155] text-[14px]">user@financialinstitution.com</p>
    </div>
  );
}

function FieldEmail() {
  return (
    <div className="content-stretch flex flex-col gap-[8px] items-start relative shrink-0 w-full" data-name="field-email">
      <p className="[word-break:break-word] font-['Geist:SemiBold',sans-serif] font-semibold leading-[normal] relative shrink-0 text-[#0f172a] text-[13px] whitespace-nowrap">Email Address</p>
      <InputBox />
    </div>
  );
}

function Lock() {
  return (
    <div className="relative shrink-0 size-[16px]" data-name="lock">
      <svg className="absolute block inset-0 size-full" fill="none" height="16" preserveAspectRatio="none" viewBox="0 0 16 16" width="16">
        <g id="lock">
          <path d={svgPaths.p241025a0} id="Vector" stroke="#94A3B8" strokeLinecap="round" strokeWidth="2" />
        </g>
      </svg>
    </div>
  );
}

function InputBox1() {
  return (
    <div className="bg-[#f8fafc] content-stretch flex gap-[10px] items-center p-[12px] relative rounded-[8px] shrink-0 w-full" data-name="input-box">
      <div aria-hidden className="absolute border border-[#f1f5f9] border-solid inset-0 pointer-events-none rounded-[8px]" />
      <Lock />
      <p className="[word-break:break-word] flex-[1_0_0] font-['Geist:Regular',sans-serif] font-normal leading-[normal] min-w-px relative text-[#94a3b8] text-[14px]">••••••••••••</p>
      <p className="[word-break:break-word] font-['Geist:Bold',sans-serif] font-bold leading-[normal] relative shrink-0 text-[#3b82f6] text-[12px] whitespace-nowrap">Show</p>
    </div>
  );
}

function FieldPassword() {
  return (
    <div className="content-stretch flex flex-col gap-[8px] items-start relative shrink-0 w-full" data-name="field-password">
      <p className="[word-break:break-word] font-['Geist:SemiBold',sans-serif] font-semibold leading-[normal] relative shrink-0 text-[#0f172a] text-[13px] whitespace-nowrap">Security Password</p>
      <InputBox1 />
    </div>
  );
}

function RememberBox() {
  return (
    <div className="content-stretch flex gap-[8px] items-center relative shrink-0" data-name="remember-box">
      <div className="bg-white border border-[#94a3b8] border-solid relative rounded-[4px] shrink-0 size-[16px]" data-name="checkbox" />
      <p className="[word-break:break-word] font-['Geist:Regular',sans-serif] font-normal leading-[normal] relative shrink-0 text-[#334155] text-[13px] whitespace-nowrap">Remember active workspace</p>
    </div>
  );
}

function OptionsRow() {
  return (
    <div className="content-stretch flex items-center justify-between relative shrink-0 w-full" data-name="options-row">
      <RememberBox />
      <p className="[word-break:break-word] font-['Geist:SemiBold',sans-serif] font-semibold leading-[normal] relative shrink-0 text-[#3b82f6] text-[13px] whitespace-nowrap">Forgot Password?</p>
    </div>
  );
}

function InputsGroup() {
  return (
    <div className="content-stretch flex flex-col gap-[20px] items-start relative shrink-0 w-full" data-name="inputs-group">
      <FieldEmail />
      <FieldPassword />
      <OptionsRow />
    </div>
  );
}

function BtnPrimary() {
  return (
    <div className="bg-[#0f172a] content-stretch flex items-center justify-center px-[24px] py-[12px] relative rounded-[8px] shrink-0 w-full" data-name="btn-primary">
      <p className="[word-break:break-word] font-['Geist:SemiBold',sans-serif] font-semibold leading-[normal] relative shrink-0 text-[14px] text-white whitespace-nowrap">Sign In Securely</p>
    </div>
  );
}

function SocialDivider() {
  return (
    <div className="content-stretch flex gap-[8px] items-center relative shrink-0 w-full" data-name="social-divider">
      <div className="flex-[1_0_0] h-0 min-w-px relative" data-name="Line">
        <div className="absolute inset-[-1px_0_0_0]">
          <svg className="block size-full" fill="none" height="1" preserveAspectRatio="none" viewBox="0 0 129.5 1" width="129.5">
            <line id="Line" stroke="#F1F5F9" x2="129.5" y1="0.5" y2="0.5" />
          </svg>
        </div>
      </div>
      <p className="[word-break:break-word] font-['Geist:Regular',sans-serif] font-normal leading-[normal] relative shrink-0 text-[#94a3b8] text-[11px] uppercase whitespace-nowrap">or authenticate with</p>
      <div className="flex-[1_0_0] h-0 min-w-px relative" data-name="Line">
        <div className="absolute inset-[-1px_0_0_0]">
          <svg className="block size-full" fill="none" height="1" preserveAspectRatio="none" viewBox="0 0 129.5 1" width="129.5">
            <line id="Line" stroke="#F1F5F9" x2="129.5" y1="0.5" y2="0.5" />
          </svg>
        </div>
      </div>
    </div>
  );
}

function CircleX() {
  return (
    <div className="relative shrink-0 size-[16px]" data-name="circle-x">
      <svg className="absolute block inset-0 size-full" fill="none" height="16" preserveAspectRatio="none" viewBox="0 0 16 16" width="16">
        <g clipPath="url(#clip0_0_8)" id="circle-x">
          <path d={svgPaths.p30250f00} id="Vector" stroke="#0F172A" strokeLinecap="round" strokeWidth="2" />
        </g>
        <defs>
          <clipPath id="clip0_0_8">
            <rect fill="white" height="16" width="16" />
          </clipPath>
        </defs>
      </svg>
    </div>
  );
}

function SocialBtn() {
  return (
    <div className="bg-white content-stretch flex flex-[1_0_26px] gap-[8px] items-center justify-center min-w-px p-[12px] relative rounded-[8px]" data-name="social-btn">
      <div aria-hidden className="absolute border border-[#f1f5f9] border-solid inset-0 pointer-events-none rounded-[8px]" />
      <CircleX />
      <p className="[word-break:break-word] font-['Geist:SemiBold',sans-serif] font-semibold leading-[normal] relative shrink-0 text-[#0f172a] text-[13px] whitespace-nowrap">Google SSO</p>
    </div>
  );
}

function CircleX1() {
  return (
    <div className="relative shrink-0 size-[16px]" data-name="circle-x">
      <svg className="absolute block inset-0 size-full" fill="none" height="16" preserveAspectRatio="none" viewBox="0 0 16 16" width="16">
        <g clipPath="url(#clip0_0_8)" id="circle-x">
          <path d={svgPaths.p30250f00} id="Vector" stroke="#0F172A" strokeLinecap="round" strokeWidth="2" />
        </g>
        <defs>
          <clipPath id="clip0_0_8">
            <rect fill="white" height="16" width="16" />
          </clipPath>
        </defs>
      </svg>
    </div>
  );
}

function SocialBtn1() {
  return (
    <div className="bg-white content-stretch flex flex-[1_0_26px] gap-[8px] items-center justify-center min-w-px p-[12px] relative rounded-[8px]" data-name="social-btn">
      <div aria-hidden className="absolute border border-[#f1f5f9] border-solid inset-0 pointer-events-none rounded-[8px]" />
      <CircleX1 />
      <p className="[word-break:break-word] font-['Geist:SemiBold',sans-serif] font-semibold leading-[normal] relative shrink-0 text-[#0f172a] text-[13px] whitespace-nowrap">Microsoft Active Directory</p>
    </div>
  );
}

function SocialsRow() {
  return (
    <div className="content-stretch flex gap-[12px] items-start relative shrink-0 w-full" data-name="socials-row">
      <SocialBtn />
      <SocialBtn1 />
    </div>
  );
}

function ActionsGroup() {
  return (
    <div className="content-stretch flex flex-col gap-[16px] items-start relative shrink-0 w-full" data-name="actions-group">
      <BtnPrimary />
      <SocialDivider />
      <SocialsRow />
    </div>
  );
}

function RegisterRow() {
  return (
    <div className="[word-break:break-word] content-stretch flex gap-[4px] items-start justify-center leading-[normal] relative shrink-0 text-[13px] w-full whitespace-nowrap" data-name="register-row">
      <p className="font-['Geist:Regular',sans-serif] font-normal relative shrink-0 text-[#334155]">{`Don't have an enterprise workspace?`}</p>
      <p className="font-['Geist:Bold',sans-serif] font-bold relative shrink-0 text-[#3b82f6]">Register</p>
    </div>
  );
}

function FormFlow() {
  return (
    <div className="content-stretch flex flex-col gap-[32px] items-start relative shrink-0 w-[400px]" data-name="form-flow">
      <FormHeader />
      <InputsGroup />
      <ActionsGroup />
      <RegisterRow />
    </div>
  );
}

function UserCircle() {
  return (
    <div className="relative shrink-0 size-[12px]" data-name="user-circle">
      <svg className="absolute block inset-0 size-full" fill="none" height="12" preserveAspectRatio="none" viewBox="0 0 12 12" width="12">
        <g clipPath="url(#clip0_0_4)" id="user-circle">
          <path d={svgPaths.p1f01eb00} id="Vector" stroke="white" strokeLinecap="round" strokeWidth="2" />
        </g>
        <defs>
          <clipPath id="clip0_0_4">
            <rect fill="white" height="12" width="12" />
          </clipPath>
        </defs>
      </svg>
    </div>
  );
}

function SelectorChip() {
  return (
    <div className="bg-[#0f172a] content-stretch flex flex-[1_0_0] gap-[6px] items-center justify-center min-w-px px-[10px] py-[8px] relative rounded-[8px]" data-name="selector-chip">
      <UserCircle />
      <p className="[word-break:break-word] font-['Geist:SemiBold',sans-serif] font-semibold leading-[normal] relative shrink-0 text-[12px] text-white whitespace-nowrap">Individual</p>
    </div>
  );
}

function Building() {
  return (
    <div className="relative shrink-0 size-[12px]" data-name="building">
      <svg className="absolute block inset-0 size-full" fill="none" height="12" preserveAspectRatio="none" viewBox="0 0 12 12" width="12">
        <g id="building">
          <path d={svgPaths.p3ddcec80} id="Vector" stroke="#334155" strokeLinecap="round" strokeWidth="2" />
        </g>
      </svg>
    </div>
  );
}

function SelectorChip1() {
  return (
    <div className="bg-[#f8fafc] content-stretch flex flex-[1_0_22px] gap-[6px] items-center justify-center min-w-px px-[10px] py-[8px] relative rounded-[8px]" data-name="selector-chip">
      <div aria-hidden className="absolute border border-[#f1f5f9] border-solid inset-0 pointer-events-none rounded-[8px]" />
      <Building />
      <p className="[word-break:break-word] font-['Geist:SemiBold',sans-serif] font-semibold leading-[normal] relative shrink-0 text-[#334155] text-[12px] whitespace-nowrap">Bank</p>
    </div>
  );
}

function ShieldAlert() {
  return (
    <div className="relative shrink-0 size-[12px]" data-name="shield-alert">
      <svg className="absolute block inset-0 size-full" fill="none" height="12" preserveAspectRatio="none" viewBox="0 0 12 12" width="12">
        <g clipPath="url(#clip0_0_10)" id="shield-alert">
          <path d={svgPaths.pbaa4a00} id="Vector" stroke="#334155" strokeLinecap="round" strokeWidth="2" />
        </g>
        <defs>
          <clipPath id="clip0_0_10">
            <rect fill="white" height="12" width="12" />
          </clipPath>
        </defs>
      </svg>
    </div>
  );
}

function SelectorChip2() {
  return (
    <div className="bg-[#f8fafc] content-stretch flex flex-[1_0_22px] gap-[6px] items-center justify-center min-w-px px-[10px] py-[8px] relative rounded-[8px]" data-name="selector-chip">
      <div aria-hidden className="absolute border border-[#f1f5f9] border-solid inset-0 pointer-events-none rounded-[8px]" />
      <ShieldAlert />
      <p className="[word-break:break-word] font-['Geist:SemiBold',sans-serif] font-semibold leading-[normal] relative shrink-0 text-[#334155] text-[12px] whitespace-nowrap">NBFC</p>
    </div>
  );
}

function HeartPulse() {
  return (
    <div className="relative shrink-0 size-[12px]" data-name="heart-pulse">
      <svg className="absolute block inset-0 size-full" fill="none" height="12" preserveAspectRatio="none" viewBox="0 0 12 12" width="12">
        <g clipPath="url(#clip0_0_15)" id="heart-pulse">
          <path d={svgPaths.p493b700} id="Vector" stroke="#334155" strokeLinecap="round" strokeWidth="2" />
        </g>
        <defs>
          <clipPath id="clip0_0_15">
            <rect fill="white" height="12" width="12" />
          </clipPath>
        </defs>
      </svg>
    </div>
  );
}

function SelectorChip3() {
  return (
    <div className="bg-[#f8fafc] content-stretch flex flex-[1_0_22px] gap-[6px] items-center justify-center min-w-px px-[10px] py-[8px] relative rounded-[8px]" data-name="selector-chip">
      <div aria-hidden className="absolute border border-[#f1f5f9] border-solid inset-0 pointer-events-none rounded-[8px]" />
      <HeartPulse />
      <p className="[word-break:break-word] font-['Geist:SemiBold',sans-serif] font-semibold leading-[normal] relative shrink-0 text-[#334155] text-[12px] whitespace-nowrap">Insurance</p>
    </div>
  );
}

function SelectorGrid() {
  return (
    <div className="content-stretch flex gap-[8px] items-start relative shrink-0 w-full" data-name="selector-grid">
      <SelectorChip />
      <SelectorChip1 />
      <SelectorChip2 />
      <SelectorChip3 />
    </div>
  );
}

function UserTypeSelector() {
  return (
    <div className="content-stretch flex flex-col gap-[16px] items-start relative shrink-0 w-[400px]" data-name="user-type-selector">
      <p className="[word-break:break-word] font-['Geist:Bold',sans-serif] font-bold leading-[normal] relative shrink-0 text-[#94a3b8] text-[12px] text-center uppercase w-full">Select Active User Register</p>
      <SelectorGrid />
    </div>
  );
}

export default function RightSplit() {
  return (
    <div className="content-stretch flex flex-col items-center justify-between p-[64px] relative size-full" data-name="right-split">
      <FormFlow />
      <UserTypeSelector />
    </div>
  );
}