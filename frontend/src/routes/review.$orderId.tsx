import { useMutation } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Star } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import { ReviewsService } from "@/client"
import { AuthLayout } from "@/components/Common/AuthLayout"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { cn } from "@/lib/utils"

type ReviewSearch = { token?: string }

export const Route = createFileRoute("/review/$orderId")({
  component: ReviewPage,
  validateSearch: (search: Record<string, unknown>): ReviewSearch => ({
    token: typeof search.token === "string" ? search.token : undefined,
  }),
})

function ReviewPage() {
  const { t } = useTranslation()
  const { orderId } = Route.useParams()
  const { token } = Route.useSearch()
  const [rating, setRating] = useState(0)
  const [comment, setComment] = useState("")

  const mutation = useMutation({
    mutationFn: () =>
      ReviewsService.createReview({
        body: { order_id: orderId, rating, comment: comment || null, token },
      }),
  })

  if (mutation.isSuccess) {
    return (
      <AuthLayout>
        <div className="text-center">
          <h1 className="text-2xl font-bold">{t("review.thanks")}</h1>
          <p className="text-sm text-muted-foreground">
            {t("review.thanksSub")}
          </p>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout>
      <form
        className="flex flex-col gap-6"
        onSubmit={(e) => {
          e.preventDefault()
          if (rating >= 1 && !mutation.isPending) mutation.mutate()
        }}
      >
        <div className="text-center">
          <h1 className="text-2xl font-bold">{t("review.title")}</h1>
          <p className="text-sm text-muted-foreground">
            {t("review.subtitle")}
          </p>
        </div>

        <div className="flex justify-center gap-1">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              aria-label={t("review.stars", { n })}
              onClick={() => setRating(n)}
            >
              <Star
                className={cn(
                  "size-8",
                  n <= rating
                    ? "fill-yellow-400 text-yellow-400"
                    : "text-muted-foreground",
                )}
              />
            </button>
          ))}
        </div>

        <Input
          placeholder={t("review.commentPh")}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />

        {mutation.isError && (
          <p className="text-sm text-destructive text-center">
            {t("review.error")}
          </p>
        )}

        {rating >= 1 ? (
          <LoadingButton type="submit" loading={mutation.isPending}>
            {t("review.submit")}
          </LoadingButton>
        ) : (
          <Button type="submit" disabled>
            {t("review.chooseRating")}
          </Button>
        )}
      </form>
    </AuthLayout>
  )
}
