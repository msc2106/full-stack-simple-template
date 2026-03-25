import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import type { AxiosError } from "axios";
import { useState } from "react";
import {
  type BodyLoginLoginAccessToken as AccessToken,
  loginLoginAccessToken,
  type UserPublic,
  type UserRegister,
  usersReadUserMe,
  usersRegisterUser,
} from "@/client";
import { handleError } from "@/utils";

const isLoggedIn = () => {
  return localStorage.getItem("access_token") !== null;
};

const useAuth = () => {
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: user } = useQuery<UserPublic | undefined, Error>({
    queryKey: ["currentUser"],
    queryFn: async () => {
      const res = await usersReadUserMe();
      return res.data;
    },
    enabled: isLoggedIn(),
  });

  const signUpMutation = useMutation({
    mutationFn: (data: UserRegister) => usersRegisterUser({ body: data }),

    onSuccess: () => {
      navigate({ to: "/login" });
    },
    onError: (err: AxiosError) => {
      handleError(err);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  const login = async (data: AccessToken) => {
    const response = await loginLoginAccessToken({
      body: data,
    });
    const accessToken = response.data?.access_token;
    if (!accessToken) {
      throw new Error("No access token received");
    }
    localStorage.setItem("access_token", accessToken);
  };

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: () => {
      navigate({ to: "/" });
    },
    onError: (err: AxiosError) => {
      handleError(err);
    },
  });

  const logout = () => {
    localStorage.removeItem("access_token");
    navigate({ to: "/login" });
  };

  return {
    signUpMutation,
    loginMutation,
    logout,
    user,
    error,
    resetError: () => setError(null),
  };
};

export { isLoggedIn };
export default useAuth;
