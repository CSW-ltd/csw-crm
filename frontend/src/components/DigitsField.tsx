import { TextField, type TextFieldProps } from "@mui/material";

/** Faqat raqam qabul qiladigan maydon: STIR (9), MFO (5), hisob raqam (20), OKED (5).
 *  Chegaraga yetgach ortiqcha raqam yozilmaydi; nusxa qo'yilganda ham harf va bo'shliqlar olib tashlanadi. */
export const DIGITS = { stir: 9, inn: 9, mfo: 5, account: 20, oked: 5 } as const;

export function DigitsField({ max, value, onValue, inputProps, ...rest }: Omit<TextFieldProps, "onChange" | "value"> & {
  max: number; value: string | null | undefined; onValue: (v: string) => void }) {
  return (
    <TextField {...rest} value={value ?? ""} onChange={(e) => onValue(e.target.value.replace(/\D/g, "").slice(0, max))}
      inputProps={{ ...inputProps, inputMode: "numeric", maxLength: max, pattern: "[0-9]*" }} />
  );
}

export const onlyDigits = (v: string, max: number) => v.replace(/\D/g, "").slice(0, max);
