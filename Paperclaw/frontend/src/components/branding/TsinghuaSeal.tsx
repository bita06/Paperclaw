import sealUrl from "../../assets/tsinghua-ppm-seal.svg";

type TsinghuaSealProps = {
  className?: string;
  decorative?: boolean;
};

export function TsinghuaSeal({ className, decorative = true }: TsinghuaSealProps) {
  return <img src={sealUrl} alt={decorative ? "" : "清华大学公共管理学院院徽"} aria-hidden={decorative} className={className} />;
}
