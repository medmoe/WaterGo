import { useMutation } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Star } from "lucide-react"
import { useState } from "react"

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
  head: () => ({ meta: [{ title: "Rate your delivery" }] }),
})

function ReviewPage() {
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
          <h1 className="text-2xl font-bold">Merci !</h1>
          <p className="text-sm text-muted-foreground">
            Votre avis a bien été enregistré.
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
          <h1 className="text-2xl font-bold">Notez votre livraison</h1>
          <p className="text-sm text-muted-foreground">
            Comment s'est passée votre commande ?
          </p>
        </div>

        <div className="flex justify-center gap-1">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              aria-label={`${n} étoiles`}
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
          placeholder="Un commentaire (facultatif)"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />

        {mutation.isError && (
          <p className="text-sm text-destructive text-center">
            Ce lien n'est plus valide ou l'avis a déjà été envoyé.
          </p>
        )}

        {rating >= 1 ? (
          <LoadingButton type="submit" loading={mutation.isPending}>
            Envoyer
          </LoadingButton>
        ) : (
          <Button type="submit" disabled>
            Choisissez une note
          </Button>
        )}
      </form>
    </AuthLayout>
  )
}
