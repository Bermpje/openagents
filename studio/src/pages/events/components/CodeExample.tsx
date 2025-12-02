import React, { useMemo } from "react";
import { SchemaDefinition } from "@/services/eventExplorerService";

interface CodeExampleProps {
  title: string;
  schema: SchemaDefinition;
  language: "python" | "javascript" | "json";
}

const CodeExample: React.FC<CodeExampleProps> = ({
  title,
  schema,
  language,
}) => {
  const generateExample = (
    schema: SchemaDefinition,
    language: string
  ): string => {
    if (!schema.properties) {
      return JSON.stringify(schema.example || {}, null, 2);
    }

    const example: any = {};
    Object.entries(schema.properties).forEach(([key, prop]: [string, any]) => {
      if (prop.example !== undefined) {
        example[key] = prop.example;
      } else if (prop.default !== undefined) {
        example[key] = prop.default;
      } else {
        // Generate example based on type
        switch (prop.type) {
          case "string":
            example[key] = `"example_${key}"`;
            break;
          case "number":
            example[key] = 0;
            break;
          case "boolean":
            example[key] = true;
            break;
          case "array":
            example[key] = [];
            break;
          case "object":
            example[key] = {};
            break;
          default:
            example[key] = null;
        }
      }
    });

    if (language === "python") {
      return formatPythonExample(example);
    } else if (language === "javascript") {
      return formatJavaScriptExample(example);
    } else {
      return JSON.stringify(example, null, 2);
    }
  };

  const formatPythonExample = (obj: any): string => {
    const lines: string[] = [];
    lines.push("payload = {");
    Object.entries(obj).forEach(([key, value], index, array) => {
      const isLast = index === array.length - 1;
      const comma = isLast ? "" : ",";
      if (typeof value === "string") {
        lines.push(`    "${key}": ${value}${comma}`);
      } else if (typeof value === "object" && value !== null) {
        const nested = JSON.stringify(value, null, 2)
          .split("\n")
          .map((line, i) => (i === 0 ? line : "    " + line))
          .join("\n");
        lines.push(`    "${key}": ${nested}${comma}`);
      } else {
        lines.push(`    "${key}": ${JSON.stringify(value)}${comma}`);
      }
    });
    lines.push("}");
    return lines.join("\n");
  };

  const formatJavaScriptExample = (obj: any): string => {
    const lines: string[] = [];
    lines.push("const payload = {");
    Object.entries(obj).forEach(([key, value], index, array) => {
      const isLast = index === array.length - 1;
      const comma = isLast ? "" : ",";
      if (typeof value === "string") {
        lines.push(`  ${key}: ${value}${comma}`);
      } else if (typeof value === "object" && value !== null) {
        const nested = JSON.stringify(value, null, 2)
          .split("\n")
          .map((line, i) => (i === 0 ? line : "  " + line))
          .join("\n");
        lines.push(`  ${key}: ${nested}${comma}`);
      } else {
        lines.push(`  ${key}: ${JSON.stringify(value)}${comma}`);
      }
    });
    lines.push("};");
    return lines.join("\n");
  };

  const code = useMemo(
    () => generateExample(schema, language),
    [schema, language]
  );

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">
          {title}
        </h3>
      </div>
      <div className="p-4">
        <pre className="bg-gray-50 dark:bg-gray-900 p-3 rounded text-xs overflow-x-auto font-mono text-gray-900 dark:text-gray-100">
          <code>{code}</code>
        </pre>
      </div>
    </div>
  );
};

export default CodeExample;
