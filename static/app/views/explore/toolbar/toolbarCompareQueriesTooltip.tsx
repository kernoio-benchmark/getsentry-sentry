import {Tooltip} from '@sentry/scraps/tooltip';

import {t} from 'sentry/locale';

type Props = {
  canCompareQueries: boolean;
  children: React.ReactNode;
  hasCrossEvents: boolean;
};

export function ToolbarCompareQueries({
  canCompareQueries,
  hasCrossEvents,
  children,
}: Props) {
  const [disabled, title] = hasCrossEvents
    ? [true, t('Comparing queries is not supported during early access.')]
    : canCompareQueries
      ? [false, undefined]
      : [false, t('Add a chart to compare chart queries.')];

  return (
    <Tooltip disabled={disabled} title={title}>
      {children}
    </Tooltip>
  );
}
