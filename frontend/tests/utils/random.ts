export const randomPhoneNumber = () =>
  `+2135${Math.floor(10_000_000 + Math.random() * 89_999_999)}`
