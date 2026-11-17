import { watch } from 'vue'
import type { Ref } from 'vue'

import type { AppLocale } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'
import { useUsersStore } from '@/core/stores/usersStore'
import { composeReport, renderPdf, reportFileName, reportImageFromBlob } from '@/shared/reports'
import { fetchMeetingFileBlob } from '../api/meetingsApi'
import type { MeetingIssueLabelResponse, MeetingResponse } from '../types/meetingResponse'
import {
  CARD_IMAGE_MAX_PIXELS,
  includedCards,
  meetingNotesOptions,
  meetingNotesReportSpec,
} from '../utils/meetingNotesReport'
import type { MeetingNotesOptions } from '../utils/meetingNotesReport'

/** What a PDF of the notes is built with. */
export interface MeetingNotesBuildOptions {
  locale: AppLocale
  options: Readonly<Record<string, boolean>>
  label: Pick<MeetingIssueLabelResponse, 'issue_number' | 'draft'>
  /** The day the issue went out, as "2026-11-06", or null for a draft. */
  issuedOn: string | null
}

/** A PDF of the notes with what the server needs to check it against the notes as they are. */
export interface BuiltMeetingNotes {
  pdf: Blob
  fileName: string
  locale: AppLocale
  options: MeetingNotesOptions
  label: Pick<MeetingIssueLabelResponse, 'issue_number' | 'draft'>
  /** The cards the PDF contains at the edit versions it was built from. */
  cards: { id: number; edit_version: number }[]
}

export type BuildMeetingNotes = (request: MeetingNotesBuildOptions) => Promise<BuiltMeetingNotes>

/**
 * Builds the PDF of the meeting notes in the browser from the meeting as
 * the page holds it, with the company's branding. The card images are
 * loaded and scaled once per meeting and reused by every later build, since
 * the send dialog builds again whenever an option changes.
 */
export function useMeetingNotesPdf(meeting: Ref<MeetingResponse | null>) {
  const brandingStore = usePublicBrandingStore()
  const currentUserStore = useCurrentUserStore()
  const usersStore = useUsersStore()

  const images = new Map<number, Promise<string | null>>()
  watch(
    () => meeting.value?.id,
    () => images.clear(),
  )

  function loadImage(meetingId: number, fileId: number): Promise<string | null> {
    let image = images.get(fileId)
    if (!image) {
      image = fetchMeetingFileBlob(meetingId, fileId)
        .then((blob) => reportImageFromBlob(blob, CARD_IMAGE_MAX_PIXELS, CARD_IMAGE_MAX_PIXELS))
        .catch(() => null)
      images.set(fileId, image)
    }
    return image
  }

  const build: BuildMeetingNotes = async (request) => {
    const current = meeting.value
    if (!current) throw new Error('The meeting is not loaded.')
    const options = meetingNotesOptions(request.options)
    const spec = meetingNotesReportSpec({
      meeting: current,
      label: request.label,
      issuedOn: request.issuedOn,
      userName: (id) => usersStore.users.find((user) => user.id === id)?.full_name,
      loadImage: (fileId) => loadImage(current.id, fileId),
    })
    const definition = await composeReport(
      spec,
      {
        appName: brandingStore.appName,
        companyName: brandingStore.companyName,
        companyLogoUrl: brandingStore.companyLogoUrl,
        domain: brandingStore.domain,
        exportedBy: currentUserStore.user?.full_name ?? '',
      },
      request.locale,
      options,
    )
    return {
      pdf: await renderPdf(definition),
      fileName: reportFileName(spec.title, new Date()),
      locale: request.locale,
      options,
      label: { issue_number: request.label.issue_number, draft: request.label.draft },
      cards: includedCards(current, options).map((card) => ({ id: card.id, edit_version: card.edit_version })),
    }
  }

  return { build }
}
