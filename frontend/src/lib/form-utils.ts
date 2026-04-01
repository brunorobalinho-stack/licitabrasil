import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, type UseFormProps, type FieldValues, type Resolver } from 'react-hook-form'
import type { z } from 'zod'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function useZodForm<TOutput extends FieldValues>(
  schema: z.ZodType<TOutput, any>,
  props?: Omit<UseFormProps<TOutput>, 'resolver'>
) {
  return useForm<TOutput>({
    resolver: zodResolver(schema) as unknown as Resolver<TOutput>,
    ...props,
  })
}
