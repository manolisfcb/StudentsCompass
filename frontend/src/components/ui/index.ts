/**
 * The design system's public surface.
 *
 * A screen imports from `@/components/ui`, never from a file inside it, so a
 * component can be split or renamed without touching a feature. If a screen
 * needs a visual it cannot build from these, that is a signal the system is
 * missing a piece — not a reason to write another stylesheet.
 */
export { Alert, type AlertTone } from "@/components/ui/Alert";
export { Arrow } from "@/components/ui/Arrow";
export { Badge, type BadgeProps, type BadgeSize, type BadgeTone } from "@/components/ui/Badge";
export { Button, type ButtonProps, type ButtonSize, type ButtonVariant } from "@/components/ui/Button";
export { Card, CardFooter, CardHeader, type CardPadding, type CardProps } from "@/components/ui/Card";
export { DataTable, type Column } from "@/components/ui/DataTable";
export { FormField } from "@/components/ui/FormField";
export { Checkbox, Input, Select, Textarea } from "@/components/ui/Input";
export { Modal, type ModalSize } from "@/components/ui/Modal";
export { PageHeader, SectionHeader } from "@/components/ui/PageHeader";
export { ProgressBar, StatCard } from "@/components/ui/StatCard";
export { EmptyState, LoadingState, Spinner } from "@/components/ui/States";
export { Tabs, type TabItem } from "@/components/ui/Tabs";
