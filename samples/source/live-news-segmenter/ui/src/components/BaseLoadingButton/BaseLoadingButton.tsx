import { LoadingOutlined } from '@ant-design/icons';
import { FC, ReactNode } from 'react';

import { BaseButton } from '../BaseButton';

interface BaseLoadingButtonProps {
  loading: boolean;
  onClick: () => void;
  icon: ReactNode;
  label: string;
}

export const BaseLoadingButton: FC<BaseLoadingButtonProps> = ({
  loading,
  onClick,
  icon,
  label,
  ...props
}) => {
  return (
    <BaseButton
      variation="primary"
      onClick={onClick}
      disabled={loading}
      {...props}
    >
      {loading ? <LoadingOutlined /> : icon}
      {label}
    </BaseButton>
  );
};
