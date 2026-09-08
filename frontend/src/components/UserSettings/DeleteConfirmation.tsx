import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { useTranslation } from "react-i18next"

import { UsersService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const DeleteConfirmation = () => {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { handleSubmit } = useForm()
  const { logout } = useAuth()

  const mutation = useMutation({
    mutationFn: () => UsersService.deleteUserMe(),
    onSuccess: () => {
      showSuccessToast(t("settings.accountDeleted"))
      logout()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["currentUser"] })
    },
  })

  const onSubmit = async () => {
    mutation.mutate()
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="destructive" className="mt-3">
          {t("settings.deleteAccountTitle")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>{t("settings.confirmTitle")}</DialogTitle>
            <DialogDescription>{t("settings.confirmDesc")}</DialogDescription>
          </DialogHeader>

          <DialogFooter className="mt-4">
            <DialogClose asChild>
              <Button variant="outline" disabled={mutation.isPending}>
                {t("common.cancel")}
              </Button>
            </DialogClose>
            <LoadingButton
              variant="destructive"
              type="submit"
              loading={mutation.isPending}
            >
              {t("settings.confirm")}
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default DeleteConfirmation
