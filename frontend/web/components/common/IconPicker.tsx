'use client';

import React, { useState } from 'react';
import {
  FolderOpen,
  FileText,
  BookOpen,
  Image,
  Film,
  Music,
  Archive,
  Code,
  Database,
  FileSpreadsheet,
  Presentation,
  Pen,
  Star,
  Heart,
  Book,
  Briefcase,
  Calendar,
  Camera,
  Clock,
  Cloud,
  Coffee,
  Laptop,
  Download,
  Edit,
  Folder,
  Gift,
  Globe,
  Home,
  Key,
  Link,
  Lock,
  Mail,
  Map,
  MessageSquare,
  Monitor,
  Package,
  Paperclip,
  Phone,
  Printer,
  Settings,
  Shield,
  ShoppingCart,
  Tag,
  Trash,
  Upload,
  User,
  Users,
  Video,
  Wifi,
  Zap,
  AlertCircle,
  CheckCircle,
  Info,
  HelpCircle,
  Bell,
  Compass,
  Flag,
  MapPin,
  Building,
  GraduationCap,
  Award,
  Lightbulb,
  Puzzle,
  Rocket,
  Target,
  Trophy,
  Umbrella,
  Wind,
} from 'lucide-react';

interface IconPickerProps {
  value: string;
  onChange: (iconName: string) => void;
  label?: string;
}

// Map of icon names to components
const ICONS: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  folder: FolderOpen,
  'file-text': FileText,
  book: BookOpen,
  image: Image,
  video: Film,
  music: Music,
  archive: Archive,
  code: Code,
  database: Database,
  spreadsheet: FileSpreadsheet,
  presentation: Presentation,
  pen: Pen,
  star: Star,
  heart: Heart,
  book2: Book,
  briefcase: Briefcase,
  calendar: Calendar,
  camera: Camera,
  clock: Clock,
  cloud: Cloud,
  coffee: Coffee,
  computer: Laptop,
  download: Download,
  edit: Edit,
  folder2: Folder,
  gift: Gift,
  globe: Globe,
  home: Home,
  key: Key,
  link: Link,
  lock: Lock,
  mail: Mail,
  map: Map,
  message: MessageSquare,
  monitor: Monitor,
  package: Package,
  paperclip: Paperclip,
  phone: Phone,
  printer: Printer,
  settings: Settings,
  shield: Shield,
  cart: ShoppingCart,
  tag: Tag,
  trash: Trash,
  upload: Upload,
  user: User,
  users: Users,
  wifi: Wifi,
  zap: Zap,
  alert: AlertCircle,
  check: CheckCircle,
  info: Info,
  help: HelpCircle,
  bell: Bell,
  compass: Compass,
  flag: Flag,
  location: MapPin,
  building: Building,
  graduation: GraduationCap,
  award: Award,
  lightbulb: Lightbulb,
  puzzle: Puzzle,
  rocket: Rocket,
  target: Target,
  trophy: Trophy,
  umbrella: Umbrella,
  wind: Wind,
};

const ICON_LIST = [
  { name: 'folder', label: 'Thư mục' },
  { name: 'file-text', label: 'File' },
  { name: 'book', label: 'Sách' },
  { name: 'book2', label: 'Sách 2' },
  { name: 'image', label: 'Hình ảnh' },
  { name: 'video', label: 'Video' },
  { name: 'music', label: 'Nhạc' },
  { name: 'archive', label: 'Nén' },
  { name: 'code', label: 'Code' },
  { name: 'database', label: 'Database' },
  { name: 'spreadsheet', label: 'Excel' },
  { name: 'presentation', label: 'Slide' },
  { name: 'pen', label: 'Viết' },
  { name: 'star', label: 'Star' },
  { name: 'heart', label: 'Yêu thích' },
  { name: 'briefcase', label: 'Công việc' },
  { name: 'calendar', label: 'Lịch' },
  { name: 'camera', label: 'Camera' },
  { name: 'clock', label: 'Giờ' },
  { name: 'cloud', label: 'Cloud' },
  { name: 'coffee', label: 'Cà phê' },
  { name: 'computer', label: 'Máy tính' },
  { name: 'download', label: 'Tải về' },
  { name: 'edit', label: 'Sửa' },
  { name: 'folder2', label: 'Thư mục 2' },
  { name: 'gift', label: 'Quà' },
  { name: 'globe', label: 'Globe' },
  { name: 'home', label: 'Trang chủ' },
  { name: 'key', label: 'Khóa' },
  { name: 'link', label: 'Link' },
  { name: 'lock', label: 'Khóa' },
  { name: 'mail', label: 'Email' },
  { name: 'map', label: 'Bản đồ' },
  { name: 'message', label: 'Tin nhắn' },
  { name: 'monitor', label: 'Màn hình' },
  { name: 'package', label: 'Gói' },
  { name: 'paperclip', label: 'Đính kèm' },
  { name: 'phone', label: 'Điện thoại' },
  { name: 'printer', label: 'Máy in' },
  { name: 'settings', label: 'Cài đặt' },
  { name: 'shield', label: 'Bảo mật' },
  { name: 'cart', label: 'Giỏ hàng' },
  { name: 'tag', label: 'Nhãn' },
  { name: 'trash', label: 'Xóa' },
  { name: 'upload', label: 'Tải lên' },
  { name: 'user', label: 'Người dùng' },
  { name: 'users', label: 'Nhóm' },
  { name: 'wifi', label: 'Wifi' },
  { name: 'zap', label: 'Tia sét' },
  { name: 'alert', label: 'Cảnh báo' },
  { name: 'check', label: 'Kiểm tra' },
  { name: 'info', label: 'Thông tin' },
  { name: 'help', label: 'Trợ giúp' },
  { name: 'bell', label: 'Thông báo' },
  { name: 'compass', label: 'La bàn' },
  { name: 'flag', label: 'Cờ' },
  { name: 'location', label: 'Vị trí' },
  { name: 'building', label: 'Tòa nhà' },
  { name: 'graduation', label: 'Học vấn' },
  { name: 'award', label: 'Giải thưởng' },
  { name: 'lightbulb', label: 'Ý tưởng' },
  { name: 'puzzle', label: 'Ghép nối' },
  { name: 'rocket', label: 'Tên lửa' },
  { name: 'target', label: 'Mục tiêu' },
  { name: 'trophy', label: 'Cúp' },
  { name: 'umbrella', label: 'Ô' },
  { name: 'wind', label: 'Gió' },
];

export function IconPicker({ value, onChange, label = 'Icon' }: IconPickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');

  const selectedIcon = ICONS[value];
  const IconComponent = selectedIcon || FolderOpen;

  const filteredIcons = search
    ? ICON_LIST.filter((icon) =>
        icon.label.toLowerCase().includes(search.toLowerCase()) ||
        icon.name.toLowerCase().includes(search.toLowerCase())
      )
    : ICON_LIST;

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <div className="relative">
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-left flex items-center gap-2 hover:bg-gray-50 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
        >
          {selectedIcon ? (
            <>
              <IconComponent size={20} className="text-gray-600" />
              <span className="text-sm text-gray-700">
                {ICON_LIST.find((i) => i.name === value)?.label || value}
              </span>
            </>
          ) : (
            <span className="text-sm text-gray-400">Chọn icon...</span>
          )}
        </button>

        {isOpen && (
          <>
            <div
              className="fixed inset-0 z-10"
              onClick={() => setIsOpen(false)}
            />
            <div className="absolute z-20 mt-1 w-80 bg-white rounded-lg shadow-lg border border-gray-200 p-3 max-h-80 overflow-y-auto">
              <input
                type="text"
                placeholder="Tìm kiếm icon..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-3 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                autoFocus
              />
              <div className="grid grid-cols-6 gap-1">
                {filteredIcons.map((icon) => {
                  const Icon = ICONS[icon.name];
                  return (
                    <button
                      key={icon.name}
                      type="button"
                      onClick={() => {
                        onChange(icon.name);
                        setIsOpen(false);
                        setSearch('');
                      }}
                      className={`p-2 rounded-lg hover:bg-indigo-50 flex items-center justify-center ${
                        value === icon.name ? 'bg-indigo-100 text-indigo-600' : 'text-gray-600'
                      }`}
                      title={icon.label}
                    >
                      <Icon size={20} />
                    </button>
                  );
                })}
              </div>
              {filteredIcons.length === 0 && (
                <p className="text-sm text-gray-500 text-center py-4">
                  Không tìm thấy icon nào
                </p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// Helper function to render icon by name
export function getIconByName(name: string, size: number = 20) {
  const Icon = ICONS[name];
  if (!Icon) return <FolderOpen size={size} />;
  return <Icon size={size} />;
}

export default IconPicker;
