import {useLayoutEffect, useRef, useState} from 'react';
import styled from '@emotion/styled';

import {Button} from '@sentry/scraps/button';

import {IconContract, IconExpand} from 'sentry/icons';
import {t} from 'sentry/locale';
import {TableActionButton} from 'sentry/views/explore/components/tableActionButton';

export function useExpandoButton(onToggle: () => void) {
  const [expanded, setExpanded] = useState(false);
  const ref = useRef<HTMLButtonElement>(null);

  const [Icon, text] = expanded
    ? [IconContract, t('Collapse')]
    : [IconExpand, t('Expand')];

  const toggleExpanded = () => {
    setExpanded(!expanded);
    onToggle();
  };

  useLayoutEffect(() => {
    if (expanded) {
      ref.current?.scrollIntoView({
        block: 'start',
      });
    }
  }, [expanded]);

  const buttonProps = {
    'aria-label': text,
    icon: <Icon />,
    onClick: toggleExpanded,
    ref,
    size: 'sm',
  } as const;

  return {
    expanded,
    expando: (
      <ExpandoContainer>
        <TableActionButton
          mobile={<ExpandoButton {...buttonProps} />}
          desktop={<ExpandoButton {...buttonProps}>{text}</ExpandoButton>}
        />
      </ExpandoContainer>
    ),
  };
}

const ExpandoButton = styled(Button)`
  scroll-margin-top: 0.75rem;
`;

const ExpandoContainer = styled('div')`
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  z-index: 1;
`;
