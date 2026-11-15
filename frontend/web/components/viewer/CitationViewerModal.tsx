'use client';

import { Modal } from '@/components/ui';
import type { Citation } from '@/lib/api/types';
import { ContentViewer } from './ContentViewer';

/**
 * FR-14: opens the cited document at the cited passage. Only for a citation of the current
 * version (the caller checks `canOpenViewer`); an old version never reaches this component.
 */
export function CitationViewerModal({ citation, onClose }: { citation: Citation | null; onClose: () => void }) {
  return (
    <Modal
      open={citation !== null}
      onClose={onClose}
      size="full"
      title={citation ? `[${citation.n}] ${citation.title}` : undefined}
      description="The text the system recognized, with the cited passage highlighted."
    >
      {citation ? (
        <ContentViewer
          documentId={citation.documentId}
          versionId={citation.versionId}
          fillHeight
          highlight={{ charStart: citation.charStart, charEnd: citation.charEnd, n: citation.n, page: citation.page }}
        />
      ) : null}
    </Modal>
  );
}
