import { LucideIcon } from "lucide-react";

export default function SectionHeader({
  icon: Icon,
  title,
  iconColor = "#6366f1",
}: {
  icon: LucideIcon;
  title: string;
  iconColor?: string;
}) {
  return (
    <div className="mb-4 flex items-center gap-2">
      <div
        className="flex h-8 w-8 items-center justify-center rounded-lg"
        style={{ backgroundColor: `${iconColor}1A` }} // ~10% opacity tint
      >
        <Icon size={16} style={{ color: iconColor }} />
      </div>
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
    </div>
  );
}
