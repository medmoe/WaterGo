import { useMutation, useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"

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
    },
    onSuccess: () => {
      navigate({ to: "/" })
    },
    onError: handleError.bind(showErrorToast),
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
