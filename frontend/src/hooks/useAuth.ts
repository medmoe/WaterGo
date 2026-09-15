import { useMutation, useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { AxiosError } from "axios"
import { useTranslation } from "react-i18next"

import {
  AuthService,
  type OTPRequest,
  type OTPVerify,
  type UserPublic,
  UsersService,
} from "@/client"
import { handleError } from "@/utils"
import useCustomToast from "./useCustomToast"

const isLoggedIn = () => {
  return localStorage.getItem("access_token") !== null
}

const useAuth = () => {
  const navigate = useNavigate()
  const { showErrorToast } = useCustomToast()
  const { t } = useTranslation()

  const { data: user } = useQuery<UserPublic | null, Error>({
    queryKey: ["currentUser"],
    queryFn: async () => (await UsersService.readUserMe()).data,
    enabled: isLoggedIn(),
  })

  const requestOtpMutation = useMutation({
    mutationFn: (body: OTPRequest) => AuthService.requestOtp({ body }),
    onError: handleError.bind(showErrorToast),
  })

  const verifyOtpMutation = useMutation({
    mutationFn: async (body: OTPVerify) => {
      const res = await AuthService.verifyOtp({ body })
      localStorage.setItem("access_token", res.data.access_token)
      const me = (await UsersService.readUserMe()).data
      return me
    },
    onSuccess: (me) => {
      const dest =
        me.role === "dispatcher" || me.role === "admin"
          ? "/dispatch"
          : me.role === "driver"
            ? "/driver"
            : "/"
      navigate({ to: dest })
    },
    onError: (err: Error) => {
      // No account exists yet for this phone number - customers get one
      // automatically on their first order, dispatchers/drivers need an
      // admin to add them. Show that plainly instead of a generic error.
      if (
        err instanceof AxiosError &&
        err.response?.status === 404 &&
        err.response.data?.detail === "NO_ACCOUNT"
      ) {
        showErrorToast(t("login.noAccount"))
        return
      }
      handleError.bind(showErrorToast)(err)
    },
  })

  const logout = () => {
    localStorage.removeItem("access_token")
    navigate({ to: "/login" })
  }

  return {
    user,
    logout,
    requestOtpMutation,
    verifyOtpMutation,
  }
}

export { isLoggedIn }
export default useAuth
