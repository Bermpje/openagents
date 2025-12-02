import React from "react";
import { SchemaDefinition } from "@/services/eventExplorerService";

interface SchemaViewerProps {
  schema: SchemaDefinition;
}

const SchemaViewer: React.FC<SchemaViewerProps> = ({ schema }) => {
  const renderProperty = (
    key: string,
    prop: any,
    required: boolean = false,
    indent: number = 0
  ): React.ReactNode => {
    const type = prop.type || "any";
    const description = prop.description || "";
    const defaultValue = prop.default !== undefined ? prop.default : null;
    const example = prop.example;

    return (
      <div key={key} className="mb-2" style={{ marginLeft: `${indent * 1}rem` }}>
        <div className="flex items-start gap-2">
          <span className="font-mono text-sm font-medium text-gray-900 dark:text-gray-100">
            {key}
            {required && (
              <span className="text-red-500 dark:text-red-400 ml-1">*</span>
            )}
          </span>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            ({type}
            {defaultValue !== null && `, default: ${JSON.stringify(defaultValue)}`})
          </span>
        </div>
        {description && (
          <div className="text-sm text-gray-600 dark:text-gray-400 mt-1 ml-4">
            {description}
          </div>
        )}
        {example !== undefined && (
          <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-4 font-mono">
            example: {JSON.stringify(example)}
          </div>
        )}
        {prop.properties && (
          <div className="mt-2 ml-4">
            {Object.entries(prop.properties).map(([subKey, subProp]: [string, any]) =>
              renderProperty(
                subKey,
                subProp,
                schema.required?.includes(subKey) || false,
                indent + 1
              )
            )}
          </div>
        )}
        {prop.items && (
          <div className="mt-2 ml-4">
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Array items:
            </div>
            {renderProperty("item", prop.items, false, indent + 1)}
          </div>
        )}
      </div>
    );
  };

  if (!schema.properties) {
    return (
      <div className="text-sm text-gray-600 dark:text-gray-400">
        <span className="font-mono">{schema.type || "object"}</span>
        {schema.example && (
          <div className="mt-2">
            <pre className="bg-gray-50 dark:bg-gray-900 p-3 rounded text-xs overflow-x-auto">
              {JSON.stringify(schema.example, null, 2)}
            </pre>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {Object.entries(schema.properties).map(([key, prop]: [string, any]) =>
        renderProperty(key, prop, schema.required?.includes(key) || false)
      )}
    </div>
  );
};

export default SchemaViewer;
