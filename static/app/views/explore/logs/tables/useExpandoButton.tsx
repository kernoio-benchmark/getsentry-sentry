import {useState} from 'react';

import {Button} from '@sentry/scraps/button';

import {IconContract, IconExpand} from 'sentry/icons';
import {t} from 'sentry/locale';
import {TableActionButton} from 'sentry/views/explore/components/tableActionButton';

export function useExpandoButton(onToggle: () => void) {
  const [expanded, setExpanded] = useState(false);

  const [Icon, text] = expanded
    ? [IconContract, t('Collapse Table')]
    : [IconExpand, t('Expand Table')];

  const toggleExpanded = () => {
    setExpanded(!expanded);
    onToggle();
  };

  return {
    expanded,
    expando: (
      <TableActionButton
        mobile={
          <Button onClick={toggleExpanded} icon={<Icon />} size="sm" aria-label={text} />
        }
        desktop={
          <Button onClick={toggleExpanded} icon={<Icon />} size="sm" aria-label={text}>
            {text}
          </Button>
        }
      />
    ),
  };
}
