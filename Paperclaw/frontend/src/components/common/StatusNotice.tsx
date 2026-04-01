type StatusNoticeProps = {
  type: "success" | "error" | "info";
  message: string;
};

export function StatusNotice({ type, message }: StatusNoticeProps) {
  return <div className={`status-notice ${type}`}>{message}</div>;
}
