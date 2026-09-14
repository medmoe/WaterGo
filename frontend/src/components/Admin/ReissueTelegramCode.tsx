import { useMutation } from "@tanstack/react-query"
import { Send } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import { type UserPublic, UsersService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface ReissueTelegramCodeProps {
  user: UserPublic
}

/**
 * Standalone "(re)issue a Telegram linking code" action - for accounts that
 * are already dispatcher/driver but never got linked (e.g. promoted via role
 * update rather than created fresh) or whose code expired before they used it.
 */
const ReissueTelegramCode = ({ user }: ReissueTelegramCodeProps) => {
  const { t } = useTranslation()
  const [code, setCode] = useState<string | null>(null)
  const { showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () =>
      UsersService.reissueTelegramLinkCode({ path: { user_id: user.id } }),
    onSuccess: (res) => setCode(res.data.code),
    onError: handleError.bind(showErrorToast),
  })

  if (user.role !== "dispatcher" && user.role !== "driver") {
    return null
  }

  return (
    <>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => mutation.mutate()}
      >
        <Send />
        {t("admin.getTelegramCode")}
      </DropdownMenuItem>
      <Dialog open={code !== null} onOpenChange={(o) => !o && setCode(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t("admin.telegramCodeTitle")}</DialogTitle>
            <DialogDescription>
              {code ? t("admin.telegramCodeHelp", { code }) : null}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col items-center gap-4 py-4">
            <code className="rounded-md bg-muted px-4 py-2 text-2xl font-bold tracking-widest">
              {code}
            </code>
            <Button onClick={() => setCode(null)}>{t("admin.done")}</Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default ReissueTelegramCode
