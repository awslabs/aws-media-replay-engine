import { Table, TableBody, TableHead } from '@aws-amplify/ui-react';
import { BaseTableRowProps, ForwardRefPrimitive } from '@aws-amplify/ui-react';
import { FC, ReactElement } from 'react';

import { AWS_DARKER } from '@src/theme';

type TableRowNode = ReactElement<ForwardRefPrimitive<BaseTableRowProps, 'tr'>>;

interface BaseTableProps {
  tableHead: TableRowNode;
  tableBody: TableRowNode[];
}

export const BaseTable: FC<BaseTableProps> = ({ tableHead, tableBody }) => {
  return (
    <Table caption="" highlightOnHover={true} backgroundColor={AWS_DARKER}>
      <TableHead>{tableHead}</TableHead>
      <TableBody>{tableBody.map((row) => row)}</TableBody>
    </Table>
  );
};
